from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.model.notification import NotificationType


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    remittance_id: UUID | None
    document_id: UUID | None
    type: NotificationType
    title: str
    message: str
    read_at: datetime | None
    created_at: datetime


class NotificationSummary(BaseModel):
    unread_count: int
