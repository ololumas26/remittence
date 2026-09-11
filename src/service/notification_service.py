from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from src.exception.exceptions import InvalidIdentifierError, ResourceNotFoundError
from src.model.document import Document
from src.model.notification import Notification, NotificationType
from src.model.remittance import Remittance
from src.model.repo.notification_repo import NotificationRepository


class NotificationService:
    def __init__(self, notification_repository: NotificationRepository):
        self.notification_repo = notification_repository

    @staticmethod
    def for_remittance_created(remittance: Remittance) -> Notification:
        if remittance.client_id is None:
            raise ValueError("Não é possível notificar uma remessa sem cliente")

        amount = Decimal(remittance.amount).quantize(Decimal("0.01"))
        return Notification(
            client_id=remittance.client_id,
            remittance_id=remittance.id,
            type=NotificationType.REMITTANCE_CREATED,
            title="Remessa criada",
            message=f"A tua remessa de {amount} EUR para {remittance.recipient_name} foi criada.",
        )

    @staticmethod
    def for_document_approved(document: Document) -> Notification:
        return Notification(
            client_id=document.client_id,
            document_id=document.id,
            type=NotificationType.DOCUMENT_APPROVED,
            title="Documento aprovado",
            message=f"O teu documento ({document.document_type.value}) foi aprovado.",
        )

    @staticmethod
    def for_document_rejected(document: Document, note: str) -> Notification:
        return Notification(
            client_id=document.client_id,
            document_id=document.id,
            type=NotificationType.DOCUMENT_REJECTED,
            title="Documento rejeitado",
            message=f"O teu documento ({document.document_type.value}) foi rejeitado: {note}",
        )

    def get_all(self, client_id: UUID, limit: int, offset: int):
        return (
            self.notification_repo.get_all(client_id, limit, offset),
            self.notification_repo.count(client_id),
        )

    def count_unread(self, client_id: UUID) -> int:
        return self.notification_repo.count_unread(client_id)

    def mark_as_read(self, notification_id: str, client_id: UUID) -> Notification:
        notification = self.notification_repo.get_by_id(self._parse_id(notification_id))
        if not notification or notification.client_id != client_id:
            raise ResourceNotFoundError(f"Notificação com id {notification_id} não encontrada")

        if notification.read_at is None:
            notification.read_at = datetime.now(timezone.utc)
            notification = self.notification_repo.save(notification)

        return notification

    def mark_all_as_read(self, client_id: UUID) -> int:
        return self.notification_repo.mark_all_as_read(client_id)

    @staticmethod
    def _parse_id(notification_id: str) -> UUID:
        try:
            return UUID(str(notification_id))
        except (ValueError, AttributeError, TypeError):
            raise InvalidIdentifierError(f"'{notification_id}' não é um identificador válido")
