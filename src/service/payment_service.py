import logging
from datetime import datetime, timezone
from decimal import Decimal

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
from src.exception.exceptions import InvalidPaymentCallbackError, InvalidPaymentDataError

logger = logging.getLogger("remittance")


class ProcessarPagamento(ABC):
    @abstractmethod
    def execute(self, payment: Payment, create_payment: CreatePayment) -> str:
        raise NotImplemented


class Mbway(ProcessarPagamento):
    method = 'mbway'

    def __init__(self, gateway: StripeMbwayGateway | None = None):
        self.gateway = gateway or StripeMbwayGateway()

    def execute(self, payment: Payment, create_payment: CreatePayment) -> str:
        # O número de telemóvel tem de vir explícito no bloco 'mbway' do pedido — é para esse
        # número que a Stripe envia a notificação push a pedir a confirmação do pagamento.
        phone_number = create_payment.mbway.phone_number if create_payment.mbway else None

        if not phone_number:
            raise InvalidPaymentDataError("Número de telemóvel em falta para o pagamento MB WAY")

        # Id do PaymentIntent da Stripe: é o que liga o webhook assíncrono de confirmação (ver
        # PaymentService.handle_stripe_webhook) de volta a este Payment.
        return self.gateway.request_payment(
            order_id=str(payment.id),
            amount=payment.amount,
            phone_number=phone_number,
        )


class CreditDebitCard(ProcessarPagamento):
    method = 'credit_debit'
    def execute(self, payment: Payment, create_payment: CreatePayment) -> str:
        """Chamar a stripe e processar o pagamwnto por cartão de crédito ou débito"""
        print("Executando pagamento por cartão")
        return "ID do pagamento"

class MultibankReference(ProcessarPagamento):
    method = 'multibank'
    def execute(self, payment: Payment, create_payment: CreatePayment) -> str:
        """Chamar a stripe e processar o pagamwnto por referência multibanco"""
        print("Executando pagamento por multibanco")
        return "ID do pagamento"

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

    def execute_payment(self, create_payment : CreatePayment, ip_address: str = "") -> Remittance:
        create_remittance = create_payment.remittance
        payment_method = create_remittance.payment_method
        processor : ProcessarPagamento = self.payment_methods[payment_method]

        # O Payment é construído (id incluído — default_factory=uuid.uuid4 em Payment, gerado em
        # memória, não pela base de dados) antes de chamar o processador, porque o próprio id
        # serve de orderId/idempotency key no pedido à Stripe: é assim que o webhook de
        # confirmação (que só traz o id do PaymentIntent) consegue voltar a encontrar este
        # Payment depois — ver provider_reference guardado abaixo.
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
        provider_reference = processor.execute(payment, create_payment)
        payment.provider_reference = provider_reference

        remittance, client = self.remittance_service.build_remittance(create_remittance, ip_address=ip_address)
        notification = NotificationService.for_remittance_created(remittance)
        saved_payment, saved_remittance = self.payment_transaction_repo.save(
            payment, remittance, notification
        )
        self.remittance_service.send_created_email(client, saved_remittance)
        return saved_remittance

    def handle_stripe_webhook(self, payload: bytes, signature: str | None) -> None:
        """Trata um webhook da Stripe (ver payment_controller.stripe_webhook). Nunca chamado pelo
        cliente da app — só a própria Stripe invoca isto. Só dois tipos de evento nos interessam
        para já (MB WAY): pagamento confirmado ou pagamento falhado; qualquer outro é ignorado."""

        event = self.mbway_gateway.verify_webhook(payload, signature)

        if event["type"] == EVENT_PAYMENT_SUCCEEDED:
            self._confirm_payment(event["data"]["object"])
        elif event["type"] == EVENT_PAYMENT_FAILED:
            self._fail_payment(event["data"]["object"])

    def _get_payment_for_callback(self, payment_intent: dict) -> Payment:
        provider_reference = payment_intent.get("id")
        payment = self.payment_repo.get_by_provider_reference(provider_reference) if provider_reference else None

        if not payment:
            logger.warning("Webhook Stripe para um provider_reference desconhecido: %s", provider_reference)
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
        payment.updated_at = datetime.now(timezone.utc)

        return self.payment_repo.save(payment)

# TODO: Pensar em como adicionar os pedido de remessa em uma fila reolver cada uma sob demanda Yield
# TODO: Configurar autenticação com o google -> Deixar para quando ter os primeiros cliente
# TODO: SOCKET para comunicação em tempo real do lado da administração quando houver pedido de remessa.
