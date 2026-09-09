import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from src.dto.payment_dto import CreatePayment
from abc import ABC, abstractmethod
from src.service.remittance_service import RemittanceService
from src.model.payment_method import PaymentMethod
from src.model.payment import Payment, PaymentStatus
from src.model.remittance import Remittance
from src.model.repo.payment_repo import PaymentRepository
from src.model.repo.payment_transaction_repo import PaymentTransactionRepository
from src.service.notification_service import NotificationService
from src.external.service.ifthenpay_mbway_service import IfthenpayMbwayGateway
from src.exception.exceptions import InvalidPaymentDataError, InvalidPaymentCallbackError

load_dotenv()

logger = logging.getLogger("remittance")

# Chave secreta própria (nunca devolvida pela ifthenpay — é definida por nós na ativação do
# callback, ver .env.example) usada para confirmar que um pedido a chegar a
# confirm_mbway_payment veio mesmo da ifthenpay e não de alguém a tentar forjar uma confirmação
# de pagamento.
IFTHENPAY_MBWAY_CALLBACK_KEY = os.environ.get("IFTHENPAY_MBWAY_CALLBACK_KEY")


class ProcessarPagamento(ABC):
    @abstractmethod
    def execute(self, payment: Payment, create_payment: CreatePayment) -> str:
        raise NotImplemented


class Mbway(ProcessarPagamento):
    method = 'mbway'

    def __init__(self, gateway: IfthenpayMbwayGateway | None = None):
        self.gateway = gateway or IfthenpayMbwayGateway()

    def execute(self, payment: Payment, create_payment: CreatePayment) -> str:
        # O número de telemóvel tem de vir explícito no bloco 'mbway' do pedido — é para esse
        # número que a ifthenpay envia a notificação push a pedir a confirmação do pagamento.
        phone_number = create_payment.mbway.phone_number if create_payment.mbway else None

        if not phone_number:
            raise InvalidPaymentDataError("Número de telemóvel em falta para o pagamento MB WAY")

        # RequestId da ifthenpay: é o que liga o callback assíncrono de confirmação (ver
        # PaymentService.confirm_mbway_payment) de volta a este Payment.
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
        mbway_gateway : IfthenpayMbwayGateway | None = None,
        mbway_callback_key : str | None = IFTHENPAY_MBWAY_CALLBACK_KEY,
    ):
        self.remittance_service = remittance_service
        self.payment_transaction_repo = payment_transaction_repository
        self.payment_repo = payment_repository
        self.mbway_callback_key = mbway_callback_key
        self.payment_methods = {
            PaymentMethod.MBWAY: Mbway(mbway_gateway),
            PaymentMethod.CARD: CreditDebitCard(),
            PaymentMethod.MULTIBANK: MultibankReference()}

    def execute_payment(self, create_payment : CreatePayment, ip_address: str = "") -> Remittance:
        create_remittance = create_payment.remittance
        payment_method = create_remittance.payment_method
        processor : ProcessarPagamento = self.payment_methods[payment_method]

        # O Payment é construído (id incluído — default_factory=uuid.uuid4 em Payment, gerado em
        # memória, não pela base de dados) antes de chamar o processador, porque o próprio id
        # serve de orderId no pedido à ifthenpay: é assim que o callback de confirmação (que só
        # traz o requestId da ifthenpay) consegue voltar a encontrar este Payment depois — ver
        # provider_reference guardado abaixo.
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

    def confirm_mbway_payment(self, antiphishing_key: str, transaction_id: str, amount: str) -> Payment:
        """Trata o callback assíncrono da ifthenpay que confirma um pagamento MB WAY como pago.
        Nunca é chamado pelo cliente da app — é a própria ifthenpay que invoca isto (ver
        payment_controller.mbway_callback). Idempotente: um callback repetido para um pagamento já
        confirmado é um sucesso silencioso, não um erro (a ifthenpay pode reenviar o mesmo
        callback mais que uma vez)."""

        if not self.mbway_callback_key or antiphishing_key != self.mbway_callback_key:
            logger.warning("Callback MB WAY recusado: chave antiphishing inválida (transaction_id=%s)", transaction_id)
            raise InvalidPaymentCallbackError("Chave de confirmação inválida")

        payment = self.payment_repo.get_by_provider_reference(transaction_id)
        if not payment:
            logger.warning("Callback MB WAY para um provider_reference desconhecido: %s", transaction_id)
            raise InvalidPaymentCallbackError("Pagamento não encontrado")

        # Já confirmado (ex: a ifthenpay reenviou o mesmo callback) — sucesso idempotente, sem
        # repetir nenhuma validação ou efeito secundário.
        if payment.status == PaymentStatus.SUCCEEDED:
            return payment

        try:
            expected_amount = f"{payment.amount:.2f}"
        except (TypeError, ValueError):
            expected_amount = str(payment.amount)

        if str(amount).strip() != expected_amount and str(amount).strip() != str(payment.amount):
            logger.warning(
                "Callback MB WAY com valor inesperado (transaction_id=%s, esperado=%s, recebido=%s)",
                transaction_id, expected_amount, amount,
            )
            raise InvalidPaymentCallbackError("Valor do pagamento não corresponde")

        if payment.status != PaymentStatus.PENDING:
            # Estado terminal diferente (ex: FAILED) — não pisar silenciosamente.
            logger.warning(
                "Callback MB WAY para um pagamento já num estado terminal diferente (transaction_id=%s, estado=%s)",
                transaction_id, payment.status,
            )
            raise InvalidPaymentCallbackError("Pagamento já não está pendente")

        payment.status = PaymentStatus.SUCCEEDED
        payment.updated_at = datetime.now(timezone.utc)

        return self.payment_repo.save(payment)

# TODO: Tratar da questão do rate limiting para evitar abusos de chamadas a API -> FEITO
# TODO: Pensar em como adicionar os pedido de remessa em uma fila reolver cada uma sob demanda Yield
# TODO: Configurar autenticação com o google -> Deixar para quando ter os primeiros cliente
# TODO: SOCKET para comunicação em tempo real do lado da administração quando houver pedido de remessa.
