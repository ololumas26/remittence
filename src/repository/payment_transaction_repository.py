from src.model.repo.payment_transaction_repo import PaymentTransactionRepository
from sqlmodel import Session
from src.model.payment import Payment
from src.model.remittance import Remittance


class SqlPaymentTransactionRepository():

    def __init__(self, db : Session):
        self.db = db

    def save(self, payment : Payment, remittance : Remittance) -> tuple[Payment, Remittance]:

        # payment.id já existe em memória (default_factory=uuid.uuid4 em Payment, não gerado
        # pela base de dados) — por isso já podemos apontar a remessa para ele antes de qualquer
        # um dos dois ser sequer adicionado à sessão, sem precisar de um round-trip à base de
        # dados a meio da transação para descobrir o id.
        remittance.payment_id = payment.id

        self.db.add(payment)
        self.db.add(remittance)

        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(payment)
        self.db.refresh(remittance)

        return payment, remittance
