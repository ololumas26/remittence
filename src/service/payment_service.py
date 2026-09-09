from src.dto.payment_dto import CreatePayment
from abc import ABC, abstractmethod
from src.service.remittance_service import RemittanceService
from src.model.payment_method import PaymentMethod
from src.model.payment import Payment, PaymentStatus
from src.model.remittance import Remittance
from src.model.repo.payment_transaction_repo import PaymentTransactionRepository


class ProcessarPagamento(ABC):
    @abstractmethod
    def execute(self):
        raise NotImplemented


class Mbway(ProcessarPagamento):
    method = 'mbway'
    def execute(self):
        """Chamar a stripe e processar o pagamwnto por mbway"""

        print("Executando pagamento por mbway")
        return "ID do pagamento"

class CreditDebitCard(ProcessarPagamento):
    method = 'credit_debit'
    def execute(self):
        """Chamar a stripe e processar o pagamwnto por cartão de crédito ou débito"""
        print("Executando pagamento por cartão")
        return "ID do pagamento"

class MultibankReference(ProcessarPagamento):
    method = 'multibank'
    def execute(self):
        """Chamar a stripe e processar o pagamwnto por referência multibanco"""
        print("Executando pagamento por multibanco")
        return "ID do pagamento"


class PaymentService:

    def __init__(self, remittance_service : RemittanceService, payment_transaction_repository : PaymentTransactionRepository):

        self.remittance_service = remittance_service
        self.payment_transaction_repo = payment_transaction_repository
        self.payment_methods = {
            PaymentMethod.MBWAY: Mbway(),
            PaymentMethod.CARD: CreditDebitCard(),
            PaymentMethod.MULTIBANK: MultibankReference()}

    # PaymentService é o orquestrador do fluxo: cria o Payment (o "ID do pagamento" devolvido
    # pelo processador vira o provider_reference) e constrói a Remittance (validada, mas ainda
    # por gravar — ver RemittanceService.build_remittance), depois entrega os dois ao
    # PaymentTransactionRepository, que os grava numa única transação atómica: ou os dois
    # persistem, ou nenhum persiste (nunca mais um Payment "Succeeded" órfão sem remessa). Só
    # depois desse commit é que o email de remessa criada é enviado.
    def execute_payment(self, create_payment : CreatePayment, ip_address: str = "") -> Remittance:

        create_remittance = create_payment.remittance
        payment_method = create_remittance.payment_method
        processor : ProcessarPagamento = self.payment_methods[payment_method]

        provider_reference = processor.execute()

        # O Payment nasce sempre PENDING (é o default do campo, mas fica explícito aqui de
        # propósito): o stub acima ainda não fala a sério com nenhum processador, e mesmo quando
        # falar, uma chamada síncrona não confirma o pagamento — MB WAY, Multibanco e cartão só
        # confirmam via webhook assíncrono do processador (Stripe ou equivalente). É esse webhook
        # que, mais tarde, transiciona o Payment para SUCCEEDED ou FAILED (preenchendo
        # failure_reason nesse caso) — nunca este método.
        payment = Payment(
            client_id=create_remittance.client_id,
            method=payment_method,
            status=PaymentStatus.PENDING,
            amount=create_remittance.amount,
            provider_reference=provider_reference,
        )

        remittance, client = self.remittance_service.build_remittance(create_remittance, ip_address=ip_address)

        saved_payment, saved_remittance = self.payment_transaction_repo.save(payment, remittance)

        self.remittance_service.send_created_email(client, saved_remittance)

        return saved_remittance


# TODO: Implementar ainda apenas o pagamento por MBWAY
# TODO: Tratar da questão do rate limiting para evitar abusos de chamadas a API -> FEITO
# TODO: Pensar em como adicionar os pedido de remessa em uma fila reolver cada uma sob demanda Yield
# TODO: Configurar autenticação com o google -> Deixar para quando ter os primeiros cliente
# TODO: SOCKET para comunicação em tempo real do lado da administração quando houver pedido de remessa.