from src.model.repo.payment_repo import PaymentRepository
from sqlmodel import Session, select
from src.model.payment import Payment
from uuid import UUID


class SqlPaymentRepository(PaymentRepository):

    def __init__(self, db : Session):
        self.db = db

    def get_by_id(self, payment_id : UUID):
        return self.db.exec(select(Payment).where(Payment.id == payment_id)).first()

    def save(self, payment : Payment):

        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)

        return payment

    def get_by_provider_reference(self, provider_reference : str):
        return self.db.exec(
            select(Payment).where(Payment.provider_reference == provider_reference)
        ).first()
