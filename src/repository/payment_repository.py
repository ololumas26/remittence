from src.model.repo.payment_repo import PaymentRepository
from sqlmodel import Session, select, func
from src.model.payment import Payment, PaymentStatus
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

    @staticmethod
    def _apply_filters(statement, client_id : UUID | None, status : PaymentStatus | None):
        if client_id:
            statement = statement.where(Payment.client_id == client_id)

        if status:
            statement = statement.where(Payment.status == status)

        return statement

    def get_all(
        self, limit : int, offset : int, order_by : str, client_id : UUID | None = None,
        status : PaymentStatus | None = None,
    ):
        order_column = getattr(Payment, order_by)
        statement = select(Payment)
        statement = self._apply_filters(statement, client_id, status)
        # .desc() sempre — mesma convenção de SqlRemittanceRepository.get_all: quem lista
        # pagamentos quer sempre o mais recente primeiro.
        statement = statement.order_by(order_column.desc()).limit(limit).offset(offset)

        return self.db.exec(statement).all()

    def count(self, client_id : UUID | None = None, status : PaymentStatus | None = None) -> int:
        statement = select(func.count()).select_from(Payment)
        statement = self._apply_filters(statement, client_id, status)

        return self.db.exec(statement).one()
