from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import update
from sqlmodel import Session, func, select

from src.model.notification import Notification
from src.model.repo.notification_repo import NotificationRepository


class SqlNotificationRepository(NotificationRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, notification_id: UUID) -> Notification | None:
        return self.db.exec(select(Notification).where(Notification.id == notification_id)).first()

    def get_all(self, client_id: UUID, limit: int, offset: int) -> list[Notification]:
        statement = (
            select(Notification)
            .where(Notification.client_id == client_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.exec(statement).all())

    def count(self, client_id: UUID) -> int:
        statement = select(func.count()).select_from(Notification).where(Notification.client_id == client_id)
        return self.db.exec(statement).one()

    def count_unread(self, client_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.client_id == client_id, Notification.read_at.is_(None))
        )
        return self.db.exec(statement).one()

    def save(self, notification: Notification) -> Notification:
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_all_as_read(self, client_id: UUID) -> int:
        statement = (
            update(Notification)
            .where(Notification.client_id == client_id, Notification.read_at.is_(None))
            .values(read_at=datetime.now(timezone.utc))
        )
        result = self.db.exec(statement)
        self.db.commit()
        return result.rowcount or 0
