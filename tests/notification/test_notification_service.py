from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

# Carrega os modelos relacionados antes de o SQLAlchemy configurar os mappers de Client.
from src.model.document import Document  # noqa: F401
from src.model.payment import Payment  # noqa: F401
from src.model.recipient import Recipient  # noqa: F401
from src.exception.exceptions import InvalidIdentifierError, ResourceNotFoundError
from src.model.document import DocumentType
from src.model.notification import Notification, NotificationType
from src.service.notification_service import NotificationService


class FakeNotificationRepository:
    def __init__(self, notifications: list[Notification] | None = None):
        self.notifications = notifications or []

    def get_by_id(self, notification_id):
        return next((item for item in self.notifications if item.id == notification_id), None)

    def get_all(self, client_id, limit, offset):
        owned = [item for item in self.notifications if item.client_id == client_id]
        return owned[offset : offset + limit]

    def count(self, client_id):
        return sum(item.client_id == client_id for item in self.notifications)

    def count_unread(self, client_id):
        return sum(
            item.client_id == client_id and item.read_at is None
            for item in self.notifications
        )

    def save(self, notification):
        return notification

    def mark_all_as_read(self, client_id):
        updated = 0
        for item in self.notifications:
            if item.client_id == client_id and item.read_at is None:
                item.read_at = datetime.now(timezone.utc)
                updated += 1
        return updated


def test_builds_remittance_created_notification():
    client_id = uuid4()
    remittance_id = uuid4()
    remittance = SimpleNamespace(
        id=remittance_id,
        client_id=client_id,
        amount=Decimal("150"),
        recipient_name="Maria Silva",
    )

    notification = NotificationService.for_remittance_created(remittance)

    assert notification.client_id == client_id
    assert notification.remittance_id == remittance_id
    assert notification.type == NotificationType.REMITTANCE_CREATED
    assert notification.title == "Remessa criada"
    assert "150.00 EUR" in notification.message
    assert "Maria Silva" in notification.message


def test_builds_document_approved_notification():
    client_id = uuid4()
    document_id = uuid4()
    document = SimpleNamespace(
        id=document_id,
        client_id=client_id,
        document_type=DocumentType.BI,
    )

    notification = NotificationService.for_document_approved(document)

    assert notification.client_id == client_id
    assert notification.document_id == document_id
    assert notification.type == NotificationType.DOCUMENT_APPROVED
    assert notification.title == "Documento aprovado"
    assert DocumentType.BI.value in notification.message


def test_builds_document_rejected_notification_with_note():
    client_id = uuid4()
    document_id = uuid4()
    document = SimpleNamespace(
        id=document_id,
        client_id=client_id,
        document_type=DocumentType.PASSAPORTE,
    )

    notification = NotificationService.for_document_rejected(document, "Foto ilegível")

    assert notification.client_id == client_id
    assert notification.document_id == document_id
    assert notification.type == NotificationType.DOCUMENT_REJECTED
    assert notification.title == "Documento rejeitado"
    assert DocumentType.PASSAPORTE.value in notification.message
    assert "Foto ilegível" in notification.message


def test_mark_as_read_is_idempotent_and_restricted_to_owner():
    owner_id = uuid4()
    notification = Notification(
        client_id=owner_id,
        type=NotificationType.REMITTANCE_CREATED,
        title="Remessa criada",
        message="Mensagem",
    )
    service = NotificationService(FakeNotificationRepository([notification]))

    first = service.mark_as_read(str(notification.id), owner_id)
    first_read_at = first.read_at
    second = service.mark_as_read(str(notification.id), owner_id)

    assert first_read_at is not None
    assert second.read_at == first_read_at

    with pytest.raises(ResourceNotFoundError):
        service.mark_as_read(str(notification.id), uuid4())


def test_rejects_invalid_notification_id():
    service = NotificationService(FakeNotificationRepository())

    with pytest.raises(InvalidIdentifierError):
        service.mark_as_read("not-a-uuid", uuid4())


def test_mark_all_only_updates_the_current_client():
    client_id = uuid4()
    other_client_id = uuid4()
    notifications = [
        Notification(
            client_id=client_id,
            type=NotificationType.REMITTANCE_CREATED,
            title="Remessa criada",
            message="Mensagem",
        ),
        Notification(
            client_id=other_client_id,
            type=NotificationType.REMITTANCE_CREATED,
            title="Remessa criada",
            message="Mensagem",
        ),
    ]
    service = NotificationService(FakeNotificationRepository(notifications))

    assert service.mark_all_as_read(client_id) == 1
    assert notifications[0].read_at is not None
    assert notifications[1].read_at is None
