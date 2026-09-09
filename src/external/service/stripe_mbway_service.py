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
# notificação push no telemóvel, sem redirecionamento), por isso a Stripe notifica sempre o
# resultado final por webhook, nunca por um return_url. Ver
# PaymentService.handle_stripe_webhook.
EVENT_PAYMENT_SUCCEEDED = "payment_intent.succeeded"
EVENT_PAYMENT_FAILED = "payment_intent.payment_failed"


class StripeMbwayGateway:
    """
    Fina camada sobre a API da Stripe para iniciar (e depois confirmar, via webhook) pagamentos
    MB WAY. Tal como o gateway anterior, uma falha aqui é propagada (PaymentGatewayError) — nunca
    tratada como "melhor esforço": a remessa não avança sem um PaymentIntent aceite pela Stripe.

    O formato exato dos pedidos (payment_method_types=['mb_way'], o telemóvel a viajar em
    billing_details.phone e não num campo dedicado dentro de payment_method_data.mb_way) foi
    confirmado a partir dos stubs de tipos oficiais do SDK Python da Stripe (pacote `stripe`,
    stripe/params/_payment_intent_create_params.py) — a página de documentação específica para a
    integração "Direct API" do MB WAY não ficou acessível durante o desenvolvimento. Vale a pena
    confirmar o fluxo uma vez contra o sandbox real assim que houver credenciais.
    """

    def __init__(
        self,
        api_key: str | None = STRIPE_SECRET_KEY,
        webhook_secret: str | None = STRIPE_MBWAY_WEBHOOK_SECRET,
    ):
        self.api_key = api_key
        self.webhook_secret = webhook_secret

    def request_payment(self, order_id: str, amount: Decimal, phone_number: str) -> str:
        """Cria e confirma um PaymentIntent MB WAY. Devolve o id do PaymentIntent (ex:
        "pi_..."), guardado como Payment.provider_reference — é ele que liga o webhook de
        confirmação ao Payment certo. O PaymentIntent fica "processing" (ou equivalente) até o
        cliente confirmar no telemóvel; ver handle_stripe_webhook para a confirmação em si."""

        if not self.api_key:
            logger.error("STRIPE_SECRET_KEY não configurada — não é possível iniciar pagamentos MB WAY")
            raise PaymentGatewayError("Pagamentos MB WAY não estão configurados de momento.")

        stripe.api_key = self.api_key

        # Euros -> cêntimos (inteiro): a API da Stripe recebe sempre o valor na unidade mais
        # pequena da moeda. quantize evita problemas de arredondamento com Decimal.
        amount_in_cents = int((amount * 100).quantize(Decimal("1")))

        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_in_cents,
                currency="eur",
                payment_method_types=["mb_way"],
                payment_method_data={
                    "type": "mb_way",
                    "billing_details": {"phone": self._format_phone(phone_number)},
                },
                confirm=True,
                description=f"Sentchu - remessa {order_id}",
                metadata={"order_id": order_id},
                # Pedidos repetidos com o mesmo order_id (ex: retry de rede do lado do nosso
                # backend) nunca criam um segundo PaymentIntent na Stripe.
                idempotency_key=order_id,
            )
        except stripe.StripeError as exc:
            logger.exception("Falha ao pedir pagamento MB WAY via Stripe (order_id=%s)", order_id)
            message = getattr(exc, "user_message", None) or str(exc) or "Pedido de pagamento MB WAY recusado."
            raise PaymentGatewayError(message)

        return payment_intent.id

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

    @staticmethod
    def _format_phone(phone_number: str) -> str:
        # billing_details.phone espera formato E.164 (ex: "+351912345678"). Aceita-se aqui tanto
        # um número já nesse formato como só os dígitos nacionais — assume-se sempre Portugal
        # (+351), único país onde o MB WAY está disponível.
        cleaned = phone_number.strip()

        if cleaned.startswith("+"):
            return cleaned

        digits = "".join(ch for ch in cleaned if ch.isdigit())

        if digits.startswith("351") and len(digits) > 9:
            return f"+{digits}"

        return f"+351{digits}"
