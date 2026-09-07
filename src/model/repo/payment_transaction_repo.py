from abc import ABC, abstractmethod
from src.model.payment import Payment
from src.model.remittance import Remittance


class PaymentTransactionRepository(ABC):
    """
    Interface à parte de PaymentRepository/RemittanceRepository de propósito: este repositório
    não é "mais um CRUD" — é o único ponto do código onde um Payment e a Remittance que ele
    financia são gravados como uma única operação atómica (os dois persistem, ou nenhum
    persiste). PaymentRepository e RemittanceRepository continuam a existir e a dar commit
    sozinhos para os seus próprios usos independentes (mark_as_sent, a rota direta
    POST /remittance, uma futura consulta de um pagamento por id, etc.) — nenhum dos dois deixa
    de fazer isso só por este repositório existir.
    """

    @abstractmethod
    def save(self, payment : Payment, remittance : Remittance) -> tuple[Payment, Remittance]:
        raise NotImplementedError
