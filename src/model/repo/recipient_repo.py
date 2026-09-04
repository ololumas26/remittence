from abc import ABC, abstractmethod
from src.model.recipient import Recipient
from uuid import UUID


class RecipientRepository(ABC):

    @abstractmethod
    def get_by_id(self, recipient_id : UUID) -> Recipient | None:
        raise NotImplementedError

    @abstractmethod
    def get_all(self, limit : int, offset : int, order_by : str, client_id : UUID | None = None) -> list[Recipient]:
        raise NotImplementedError

    @abstractmethod
    def count(self, client_id : UUID | None = None) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_by_client_id(self, client_id : UUID) -> list[Recipient]:
        raise NotImplementedError

    @abstractmethod
    def save(self, recipient : Recipient) -> Recipient:
        raise NotImplementedError

    @abstractmethod
    def delete(self, recipient : Recipient) -> None:
        raise NotImplementedError
