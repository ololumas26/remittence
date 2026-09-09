import logging
import os
from decimal import Decimal

import stripe
from dotenv import load_dotenv

from src.exception.exceptions import InvalidPaymentCallbackError, PaymentGatewayError

load_dotenv()

logger = logging.getLogger("remittance")

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_MBWAY_WEBHOOK_SECRET = os.environ.get("STRIPE_MBWAY_WEBHOOK_SECRET")

# Eventos de PaymentIntent que nos interessam — MB WAY é "customer-initiated" (confirmação via
# notificação push no telemóvel, sem redirecionamento de volta à nossa API), por isso a Stripe
# notifica sempre o resultado final por webhook. Continuam a ser eventos de PaymentIntent, não de
# Checkout Session, mesmo depois da mudança para Checkout Sessions abaixo — a Session só existe
# para gerar a página onde o cliente confirma; o PaymentIntent por trás dela dispara os mesmos
# eventos de sempre. Ver PaymentService.handle_stripe_webhook.
EVENT_PAYMENT_SUCCEEDED = "payment_intent.succeeded"
EVENT_PAYMENT_FAILED = "payment_intent.payment_failed"


class StripeMbwayGateway:
    """
    Fina camada sobre a API da Stripe para iniciar (via Checkout Session) e depois confirmar (via
    webhook) pagamentos MB WAY. Uma falha aqui é sempre propagada (PaymentGatewayError) — nunca
    tratada como "melhor esforço": a remessa não avança sem uma Checkout Session aceite pela
    Stripe.

    Porquê Checkout Session e não PaymentIntent.create(confirm=True) diretamente (como esta
    classe fazia antes): confirmámos, contra a documentação oficial do MB WAY e contra o
    comportamento reportado pelo próprio utilizador (recebia a notificação push via Checkout mas
    não via este gateway), que a notificação para o telemóvel do cliente só é disparada quando a
    confirmação do PaymentIntent acontece do lado do cliente (stripe.confirmMbWayPayment, com a
    chave pública) — nunca quando é o servidor a confirmar com a chave secreta, como fazíamos.
    O SDK nativo da Stripe para React Native também não suporta MB WAY (só Multibanco), por isso
    a única confirmação "do lado do cliente" viável aqui é a própria página hospedada da Stripe
    (Checkout) — o frontend abre o URL devolvido por create_checkout_session num browser
    embutido (expo-web-browser) e volta à app via o success_url/cancel_url (deep link
    "sentchu://...").
    """

    def __init__(
        self,
        api_key: str | None = STRIPE_SECRET_KEY,
        webhook_secret: str | None = STRIPE_MBWAY_WEBHOOK_SECRET,
    ):
        self.api_key = api_key
        self.webhook_secret = webhook_secret

    def create_checkout_session(
        self,
        order_id: str,
        amount: Decimal,
        success_url: str,
        cancel_url: str,
        customer_email: str | None = None,
    ) -> tuple[str, str]:
        """Cria uma Stripe Checkout Session para um pagamento MB WAY. Devolve
        (checkout_url, session_id): checkout_url é o URL da página hospedada da Stripe para onde
        o frontend deve navegar/abrir num browser embutido; session_id ("cs_...") é guardado
        como Payment.provider_reference até o webhook confirmar/falhar o pagamento e o
        substituir pelo id do PaymentIntent real (ver PaymentService._confirm_payment).

        Ao contrário do antigo PaymentIntent.create(confirm=True), a Checkout Session NÃO cria o
        PaymentIntent de forma síncrona — só quando o cliente avança na página — por isso não
        temos aqui o id do PaymentIntent. Para o webhook conseguir encontrar este Payment mais
        tarde sem esse id, order_id vai em payment_intent_data.metadata: assim que o
        PaymentIntent é criado (do lado da Stripe), essa metadata viaja com ele para os eventos
        payment_intent.succeeded/payment_intent.payment_failed — ver
        PaymentService._get_payment_for_callback."""

        if not self.api_key:
            logger.error("STRIPE_SECRET_KEY não configurada — não é possível iniciar pagamentos MB WAY")
            raise PaymentGatewayError("Pagamentos MB WAY não estão configurados de momento.")

        stripe.api_key = self.api_key

        # Euros -> cêntimos (inteiro): a API da Stripe recebe sempre o valor na unidade mais
        # pequena da moeda. quantize evita problemas de arredondamento com Decimal.
        amount_in_cents = int((amount * 100).quantize(Decimal("1")))

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["mb_way"],
                line_items=[
                    {
                        "price_data": {
                            "currency": "eur",
                            "unit_amount": amount_in_cents,
                            "product_data": {"name": f"Remessa Sentchu {order_id}"},
                        },
                        "quantity": 1,
                    }
                ],
                success_url=success_url,
                cancel_url=cancel_url,
                payment_intent_data={"metadata": {"order_id": order_id}},
                # Pré-preenche o email na página da Stripe com o do cliente autenticado — sem
                # isto o campo fica sempre vazio (a Stripe nunca o adivinha sozinha).
                **({"customer_email": customer_email} if customer_email else {}),
                # Pedidos repetidos com o mesmo order_id (ex: retry de rede do lado do nosso
                # backend) nunca criam uma segunda Session/PaymentIntent na Stripe.
                idempotency_key=order_id,
            )
        except stripe.StripeError as exc:
            logger.exception("Falha ao criar Checkout Session MB WAY via Stripe (order_id=%s)", order_id)
            message = getattr(exc, "user_message", None) or str(exc) or "Pedido de pagamento MB WAY recusado."
            raise PaymentGatewayError(message)

        return session.url, session.id

    def verify_webhook(self, payload: bytes, signature: str | None) -> stripe.Event:
        """Verifica a assinatura de um webhook recebido (cabeçalho Stripe-Signature) e devolve o
        Event já validado. Nunca confiar no corpo de um webhook sem passar primeiro por aqui —
        é a única coisa que garante que o pedido veio mesmo da Stripe."""

        if not self.webhook_secret:
            logger.error("STRIPE_MBWAY_WEBHOOK_SECRET não configurada — não é possível validar callbacks da Stripe")
            raise InvalidPaymentCallbackError("Confirmação de pagamentos não está configurada de momento.")

        try:
            return stripe.Webhook.construct_event(payload, signature, self.webhook_secret)
        except (stripe.SignatureVerificationError, ValueError):
            logger.warning("Callback da Stripe recusado: assinatura inválida ou payload malformado")
            raise InvalidPaymentCallbackError("Assinatura do callback inválida")
