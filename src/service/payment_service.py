import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from src.dto.payment_dto import CreatePayment
from abc import ABC, abstractmethod
from src.service.remittance_service import RemittanceService
from src.model.payment_method import PaymentMethod
from src.model.payment import Payment, PaymentStatus
from src.model.remittance import Remittance
from src.model.repo.payment_repo import PaymentRepository
from src.model.repo.payment_transaction_repo import PaymentTransactionRepository
from src.service.notification_service import NotificationService
from src.external.service.stripe_mbway_service import (
    EVENT_PAYMENT_FAILED,
    EVENT_PAYMENT_SUCCEEDED,
    StripeMbwayGateway,
)
from src.exception.exceptions import InvalidPaymentCallbackError

logger = logging.getLogger("remittance")

# Deep link de regresso à app depois da página de Checkout MB WAY (ver StripeMbwayGateway.
# create_checkout_session) — "enviando" é a mesma rota para onde resumo.tsx já navega depois de
# submeter, e o polling que já lá existe (getPaymentStatus) trata tanto o sucesso como o cancelar/
# abandonar a página da Stripe (fica Pending até dar timeout, ver enviando.tsx). Configurável por
# se um dia houver mais que um scheme (ex: build de preview vs. produção).
MBWAY_CHECKOUT_RETURN_URL = os.environ.get("MBWAY_CHECKOUT_RETURN_URL", "sentchu://enviando")


@dataclass
class PaymentExecutionResult:
    """O que um ProcessarPagamento.execute devolve: a referência a guardar em
    Payment.provider_reference e, quando o método precisa que o cliente confirme nalgum sítio
    fora da app (hoje só o MB WAY, via Checkout Session), o URL para lá navegar."""

    provider_reference: str | None
    redirect_url: str | None = None


class ProcessarPagamento(ABC):
    @abstractmethod
    def execute(self, payment: Payment, create_payment: CreatePayment) -> PaymentExecutionResult:
        raise NotImplementedError


class Mbway(ProcessarPagamento):

    method = 'mbway'

    def __init__(self, gateway: StripeMbwayGateway | None = None):
        self.gateway = gateway or StripeMbwayGateway()

    def execute(self, payment: Payment, create_payment: CreatePayment) -> PaymentExecutionResult:
        # O número de telemóvel já não é usado aqui — passou a ser a própria página de Checkout
        # da Stripe a pedi-lo ao cliente (é aí, do lado do cliente, que a confirmação realmente
        # acontece e a notificação push é disparada; ver o comentário em StripeMbwayGateway).
        # O campo mbway.phone_number no pedido fica só por compatibilidade com o frontend atual.
        checkout_url, session_id = self.gateway.create_checkout_session(
            order_id=str(payment.id),
            amount=payment.amount,
            success_url=f"{MBWAY_CHECKOUT_RETURN_URL}?id={payment.id}&paymentMethod=mbway",
            cancel_url=f"{MBWAY_CHECKOUT_RETURN_URL}?id={payment.id}&paymentMethod=mbway",
        )
        return PaymentExecutionResult(provider_reference=session_id, redirect_url=checkout_url)


class CreditDebitCard(ProcessarPagamento):

    method = 'credit_debit'
    
    def execute(self, payment: Payment, create_payment: CreatePayment) -> PaymentExecutionResult:
        """Chamar a stripe e processar o pagamwnto por cartão de crédito ou débito"""
        print("Executando pagamento por cartão")
        return PaymentExecutionResult(provider_reference="ID do pagamento")

class MultibankReference(ProcessarPagamento):
    method = 'multibank'
    def execute(self, payment: Payment, create_payment: CreatePayment) -> PaymentExecutionResult:
        """Chamar a stripe e processar o pagamwnto por referência multibanco"""
        print("Executando pagamento por multibanco")
        return PaymentExecutionResult(provider_reference="ID do pagamento")

class PaymentService:

    def __init__(
        self,
        remittance_service : RemittanceService,
        payment_transaction_repository : PaymentTransactionRepository,
        payment_repository : PaymentRepository,
        mbway_gateway : StripeMbwayGateway | None = None,
    ):
        self.remittance_service = remittance_service
        self.payment_transaction_repo = payment_transaction_repository
        self.payment_repo = payment_repository
        self.mbway_gateway = mbway_gateway or StripeMbwayGateway()
        self.payment_methods = {
            PaymentMethod.MBWAY: Mbway(self.mbway_gateway),
            PaymentMethod.CARD: CreditDebitCard(),
            PaymentMethod.MULTIBANK: MultibankReference()}

    def execute_payment(
        self, create_payment : CreatePayment, ip_address: str = ""
    ) -> tuple[Remittance, Payment, str | None]:
        create_remittance = create_payment.remittance
        payment_method = create_remittance.payment_method
        processor : ProcessarPagamento = self.payment_methods[payment_method]

        # O Payment é construído (id incluído — default_factory=uuid.uuid4 em Payment, gerado em
        # memória, não pela base de dados) antes de chamar o processador, porque o próprio id
        # serve de orderId no pedido à Stripe (metadata.order_id) — é assim que o webhook de
        # confirmação consegue voltar a encontrar este Payment depois, mesmo sem conhecer
        # antecipadamente o id do PaymentIntent (ver _get_payment_for_callback e o comentário em
        # StripeMbwayGateway.create_checkout_session sobre a Checkout Session não criar o
        # PaymentIntent de forma síncrona).
        payment = Payment(
            client_id=create_remittance.client_id,
            method=payment_method,
            status=PaymentStatus.PENDING,
            amount=create_remittance.amount,
        )

        # Tal como antes: build_remittance só valida e constrói em memória, nada é gravado até ao
        # payment_transaction_repo.save() mais abaixo — uma remessa nunca fica gravada sem que o
        # pedido de pagamento correspondente tenha sido aceite primeiro (processor.execute()
        # levanta PaymentGatewayError/InvalidPaymentDataError e interrompe tudo antes disso).
        result = processor.execute(payment, create_payment)
        payment.provider_reference = result.provider_reference

        remittance, client = self.remittance_service.build_remittance(create_remittance, ip_address=ip_address)
        notification = NotificationService.for_remittance_created(remittance)
        saved_payment, saved_remittance = self.payment_transaction_repo.save(
            payment, remittance, notification
        )
        self.remittance_service.send_created_email(client, saved_remittance)
        # (remittance, payment, redirect_url): o controller precisa dos três — payment_status
        # para o polling que o frontend já fazia (ver enviando.tsx) e redirect_url (só presente
        # para MB WAY, via Checkout Session) para o frontend saber que tem de abrir essa página
        # antes de começar a fazer polling.
        return saved_remittance, saved_payment, result.redirect_url

    def handle_stripe_webhook(self, payload: bytes, signature: str | None) -> None:
        """Trata um webhook da Stripe (ver payment_controller.stripe_webhook). Nunca chamado pelo
        cliente da app — só a própria Stripe invoca isto. Só dois tipos de evento nos interessam
        para já (MB WAY): pagamento confirmado ou pagamento falhado; qualquer outro é ignorado."""

        event = self.mbway_gateway.verify_webhook(payload, signature)

        # event["data"]["object"] vem como um stripe.PaymentIntent (StripeObject), não um dict
        # — a partir do stripe-python v15, StripeObject já não suporta .get()/[] como um dict
        # (levanta AttributeError a apontar para isto mesmo). .to_dict() converte-o (e tudo lá
        # dentro, incluindo last_payment_error) para dicts/valores simples, que é o que
        # _confirm_payment/_fail_payment esperam receber.
        if event["type"] == EVENT_PAYMENT_SUCCEEDED:
            self._confirm_payment(event["data"]["object"].to_dict())
        elif event["type"] == EVENT_PAYMENT_FAILED:
            self._fail_payment(event["data"]["object"].to_dict())

    def _get_payment_for_callback(self, payment_intent: dict) -> Payment:
        # A Checkout Session (ver StripeMbwayGateway.create_checkout_session) não cria o
        # PaymentIntent de forma síncrona, por isso Payment.provider_reference começa como o id
        # da Session ("cs_..."), não do PaymentIntent ("pi_...") — o evento do webhook só nos traz
        # este último. É por isso que a chave principal para encontrar o Payment passa a ser a
        # metadata.order_id (o próprio Payment.id, que definimos em Mbway.execute), propagada
        # automaticamente da Session para o PaymentIntent que ela cria. get_by_provider_reference
        # fica como fallback para qualquer método de pagamento futuro que continue a ter o id do
        # provider disponível de forma síncrona.
        order_id = (payment_intent.get("metadata") or {}).get("order_id")
        payment = None

        if order_id:
            try:
                payment = self.payment_repo.get_by_id(UUID(order_id))
            except (ValueError, TypeError):
                payment = None

        provider_reference = payment_intent.get("id")

        if not payment and provider_reference:
            payment = self.payment_repo.get_by_provider_reference(provider_reference)

        if not payment:
            logger.warning(
                "Webhook Stripe sem Payment correspondente (order_id=%s, provider_reference=%s)",
                order_id, provider_reference,
            )
            raise InvalidPaymentCallbackError("Pagamento não encontrado")

        expected_cents = int((payment.amount * 100).quantize(Decimal("1")))
        received_cents = payment_intent.get("amount") or payment_intent.get("amount_received")

        if received_cents is not None and int(received_cents) != expected_cents:
            logger.warning(
                "Webhook Stripe com valor inesperado (provider_reference=%s, esperado=%s cêntimos, recebido=%s)",
                provider_reference, expected_cents, received_cents,
            )
            raise InvalidPaymentCallbackError("Valor do pagamento não corresponde")

        return payment

    def _confirm_payment(self, payment_intent: dict) -> Payment:
        """Idempotente: um payment_intent.succeeded repetido para um pagamento já confirmado é
        um sucesso silencioso, não um erro (a Stripe pode reenviar o mesmo evento mais que uma
        vez — ver https://docs.stripe.com/webhooks#handle-duplicate-events)."""

        payment = self._get_payment_for_callback(payment_intent)

        if payment.status == PaymentStatus.SUCCEEDED:
            return payment

        if payment.status != PaymentStatus.PENDING:
            # Estado terminal diferente (ex: já FAILED por um evento anterior) — não pisar
            # silenciosamente um estado que já foi decidido.
            logger.warning(
                "Webhook Stripe de sucesso para um pagamento já num estado terminal diferente "
                "(provider_reference=%s, estado=%s)", payment.provider_reference, payment.status,
            )
            raise InvalidPaymentCallbackError("Pagamento já não está pendente")

        payment.status = PaymentStatus.SUCCEEDED
        # Agora que o webhook nos deu o id real do PaymentIntent, substitui o id da Checkout
        # Session que lá estava desde a criação (ver _get_payment_for_callback) — fica o valor
        # definitivo e mais útil para ir ver o pagamento no dashboard da Stripe.
        payment.provider_reference = payment_intent.get("id") or payment.provider_reference
        payment.updated_at = datetime.now(timezone.utc)

        return self.payment_repo.save(payment)

    def _fail_payment(self, payment_intent: dict) -> Payment:
        """Idempotente na mesma medida que _confirm_payment — mas nunca reverte um pagamento já
        SUCCEEDED: se a confirmação e a falha chegarem fora de ordem, o sucesso vence sempre."""

        payment = self._get_payment_for_callback(payment_intent)

        if payment.status != PaymentStatus.PENDING:
            return payment

        last_error = payment_intent.get("last_payment_error") or {}
        failure_reason = last_error.get("message") or "Pagamento MB WAY recusado ou expirado."

        payment.status = PaymentStatus.FAILED
        payment.failure_reason = failure_reason[:255]
        payment.provider_reference = payment_intent.get("id") or payment.provider_reference
        payment.updated_at = datetime.now(timezone.utc)

        return self.payment_repo.save(payment)

# TODO: Pensar em como adicionar os pedido de remessa em uma fila reolver cada uma sob demanda Yield
# TODO: Configurar autenticação com o google -> Deixar para quando ter os primeiros cliente
# TODO: SOCKET para comunicação em tempo real do lado da administração quando houver pedido de remessa.
