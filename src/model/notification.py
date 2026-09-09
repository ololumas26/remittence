from datetime import datetime, timezone
from enum import Enum
import uuid

from sqlalchemy import DateTime, Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel


class NotificationType(str, Enum):
    REMITTANCE_CREATED = "remittance_created"
    REMITTANCE_SENT = "remittance_sent"
    REMITTANCE_REJECTED = "remittance_rejected"


class Notification(SQLModel, table=True):
    __tablename__ = "notification"
    __table_args__ = (
        UniqueConstraint(
            "remittance_id",
            "type",
            name="uq_notification_remittance_type",
        ),
        Index("ix_notification_client_created_at", "client_id", "created_at"),
        Index(
            "ix_notification_client_unread",
            "client_id",
            postgresql_where=text("read_at IS NULL"),
            sqlite_where=text("read_at IS NULL"),
        ),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    client_id: uuid.UUID = Field(foreign_key="client.id", nullable=False)
    remittance_id: uuid.UUID | None = Field(
        foreign_key="remittance.id",
        nullable=True,
        default=None,
    )
    type: NotificationType = Field(nullable=False)
    title: str = Field(nullable=False, max_length=120)
    message: str = Field(nullable=False, max_length=500)
    read_at: datetime | None = Field(nullable=True, default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
