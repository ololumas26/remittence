from src.model.repo.recipient_repo import RecipientRepository
from sqlmodel import Session, select, func, nullslast
from src.model.recipient import Recipient
from src.model.remittance import Remittance
from uuid import UUID


class SqlRecipientRepository():

    def __init__(self, db : Session):
        self.db = db

    def get_by_id(self, recipient_id : str):
        return self.db.exec(select(Recipient).where(Recipient.id == recipient_id)).first()

    def get_all(self, limit : int, offset : int, order_by : str, client_id : UUID | None = None):
        if order_by == "last_sent_at":
            return self._get_all_by_last_sent_at(limit, offset, client_id)

        order_column = getattr(Recipient, order_by)
        statement = select(Recipient)

        if client_id:
            statement = statement.where(Recipient.client_id == client_id)

        # .desc() sempre — quem lista remessas/documentos/destinatários quer sempre o mais
        # recente primeiro, nunca o mais antigo.
        statement = statement.order_by(order_column.desc()).limit(limit).offset(offset)
        return self.db.exec(statement).all()

    def _get_all_by_last_sent_at(self, limit : int, offset : int, client_id : UUID | None):
        # Última remessa de cada destinatário (independente de quem é o client_id da remessa —
        # o que importa aqui é para quem foi enviada, não quem a enviou, e o dono do
        # destinatário já garante isso). Destinatários nunca usados não aparecem na subquery,
        # por isso o outerjoin + nullslast() para não os excluir, só empurrá-los para o fim.
        last_sent_subquery = (
            select(Remittance.recipient_id, func.max(Remittance.created_at).label("last_sent_at"))
            .where(Remittance.recipient_id.is_not(None))
            .group_by(Remittance.recipient_id)
            .subquery()
        )

        statement = select(Recipient).outerjoin(
            last_sent_subquery, Recipient.id == last_sent_subquery.c.recipient_id
        )

        if client_id:
            statement = statement.where(Recipient.client_id == client_id)

        statement = (
            statement.order_by(nullslast(last_sent_subquery.c.last_sent_at.desc()), Recipient.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return self.db.exec(statement).all()

    def count(self, client_id : UUID | None = None) -> int:
        statement = select(func.count()).select_from(Recipient)

        if client_id:
            statement = statement.where(Recipient.client_id == client_id)

        return self.db.exec(statement).one()

    def get_by_client_id(self, client_id : UUID):
        return self.db.exec(select(Recipient).where(Recipient.client_id == client_id)).all()

    def save(self, recipient : Recipient):

        self.db.add(recipient)
        self.db.commit()
        self.db.refresh(recipient)

        return recipient

    def delete(self, recipient : Recipient):
        self.db.delete(recipient)
        self.db.commit()
