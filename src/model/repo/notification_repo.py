from abc import ABC, abstractmethod
from uuid import UUID

from src.model.notification import Notification


class NotificationRepository(ABC):
    @abstractmethod
    def get_by_id(self, notification_id: UUID) -> Notification | None:
        raise NotImplementedError

    @abstractmethod
    def get_all(self, client_id: UUID, limit: int, offset: int) -> list[Notification]:
        raise NotImplementedError

    @abstractmethod
    def count(self, client_id: UUID) -> int:
        raise NotImplementedError

    @abstractmethod
    def count_unread(self, client_id: UUID) -> int:
        raise NotImplementedError

    @abstractmethod
    def save(self, notification: Notification) -> Notification:
        raise NotImplementedError

    @abstractmethod
    def mark_all_as_read(self, client_id: UUID) -> int:
        raise NotImplementedError
