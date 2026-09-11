from src.model.repo.remittance_repo import RemittanceRepository
from sqlmodel import Session, select, func
from src.model.remittance import Remittance, RemittanceStatus
from sqlalchemy import update
from src.model.payment import Payment, PaymentStatus
from src.model.notification import Notification
from uuid import UUID
from datetime import date, datetime, time, timezone, timedelta


class SqlRemittanceRepository():

    def __init__(self, db : Session):
        self.db = db

    def get_by_id(self, remittance_id : UUID):
        return self.db.exec(select(Remittance).where(Remittance.id == remittance_id)).first()

    def save(self, remittance : Remittance):

        self.db.add(remittance)
        self.db.commit()
        self.db.refresh(remittance)

        return remittance

    def transition_status(
        self, remittance_id: UUID, new_status: RemittanceStatus, note: str | None = None
    ) -> Remittance | None:
        if new_status not in (RemittanceStatus.SENT, RemittanceStatus.REJECTED):
            raise ValueError("A transição tem de ser para Sent ou Rejected")

        values = {"status": new_status, "updated_at": datetime.now(timezone.utc)}
        if note is not None:
            values["note"] = note

        statement = (
            update(Remittance)
            .where(Remittance.id == remittance_id,
                   Remittance.status == RemittanceStatus.IN_PROGRESS)
            .values(**values)
        )
        if new_status == RemittanceStatus.SENT:
            # Recheck payment in SQL too: a previously loaded ORM object can be stale.
            paid = select(Payment.id).where(
                Payment.id == Remittance.payment_id,
                Payment.status == PaymentStatus.SUCCEEDED,
            ).exists()
            statement = statement.where(paid)

        statement = statement.returning(Remittance.id).execution_options(synchronize_session=False)
        try:
            updated_id = self.db.execute(statement).scalar_one_or_none()
            if updated_id is None:
                self.db.rollback()
                return None
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # Reload even with expire_on_commit=False: the identity map may hold the old state.
        remittance = self.db.get(Remittance, updated_id)
        self.db.refresh(remittance)
        return remittance

    def save_with_notification(
        self, remittance: Remittance, notification: Notification
    ) -> Remittance:
        try:
            self.db.add(remittance)
            # Sem uma Relationship ORM entre Notification e Remittance, o unit of work não
            # garante a ordem dos INSERTs só porque existe uma FK na tabela. O flush mantém a
            # mesma transação, mas materializa primeiro a remessa referenciada.
            self.db.flush()
            self.db.add(notification)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(remittance)
        return remittance

    @staticmethod
    def _apply_filters(
        statement, client_id : UUID | None, status : RemittanceStatus | None,
        created_from : date | None, created_to : date | None,
    ):
        if client_id:
            statement = statement.where(Remittance.client_id == client_id)

        if status:
            statement = statement.where(Remittance.status == status)

        # created_at é datetime (com timezone). created_from/created_to são só
        # datas, por isso convertemos para o início/fim do dia em UTC para que o
        # intervalo fique inclusivo dos dois lados (ex: created_to = hoje inclui
        # remessas criadas a qualquer hora de hoje, não só até à meia-noite).
        if created_from:
            statement = statement.where(
                Remittance.created_at >= datetime.combine(created_from, time.min, tzinfo=timezone.utc)
            )

        if created_to:
            end_of_day = datetime.combine(created_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
            statement = statement.where(Remittance.created_at < end_of_day)

        return statement

    def get_all(
        self, limit : int, offset : int, order_by : str, client_id : UUID | None = None,
        status : RemittanceStatus | None = None, created_from : date | None = None,
        created_to : date | None = None,
    ):
        order_column = getattr(Remittance, order_by)
        statement = select(Remittance)
        statement = self._apply_filters(statement, client_id, status, created_from, created_to)
        # .desc() sempre — quem lista remessas/documentos/destinatários quer sempre o mais
        # recente primeiro, nunca o mais antigo.
        statement = statement.order_by(order_column.desc()).limit(limit).offset(offset)

        return self.db.exec(statement).all()

    def count(
        self, client_id : UUID | None = None, status : RemittanceStatus | None = None,
        created_from : date | None = None, created_to : date | None = None,
    ) -> int:
        statement = select(func.count()).select_from(Remittance)
        statement = self._apply_filters(statement, client_id, status, created_from, created_to)

        return self.db.exec(statement).one()
