from abc import ABC, abstractmethod
from src.model.remittance import Remittance, RemittanceStatus
from src.model.notification import Notification
from uuid import UUID
from datetime import date


class RemittanceRepository(ABC):

    @abstractmethod
    def get_by_id(self, remittance_id : UUID) -> Remittance | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, remittance : Remittance) -> Remittance:
        raise NotImplementedError

    @abstractmethod
    def save_with_notification(
        self, remittance: Remittance, notification: Notification
    ) -> Remittance:
        raise NotImplementedError

    @abstractmethod
    def transition_status(
        self, remittance_id: UUID, new_status: RemittanceStatus
    ) -> Remittance | None:
        """Commit a terminal transition only if still in progress (and paid for SENT).

        Return None when no row satisfies the conditions; never overwrite a winner.
        """
        raise NotImplementedError

    @abstractmethod
    def get_all(
        self, limit : int, offset : int, order_by : str, client_id : UUID | None = None,
        status : RemittanceStatus | None = None, created_from : date | None = None,
        created_to : date | None = None,
    ) -> list[Remittance]:
        raise NotImplementedError

    @abstractmethod
    def count(
        self, client_id : UUID | None = None, status : RemittanceStatus | None = None,
        created_from : date | None = None, created_to : date | None = None,
    ) -> int:
        raise NotImplementedError
