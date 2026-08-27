from abc import ABC, abstractmethod
from src.model.client import Client
from uuid import UUID


class ClientRepository(ABC):

    @abstractmethod
    def get_by_email(self, email : str) -> Client | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, client_id : UUID) -> Client | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_auth_user_id(self, auth_user_id : UUID) -> Client | None:
        raise NotImplementedError

    @abstractmethod
    def get_all(self, limit : int, offset : int, order_by : str) -> list[Client]:
        raise NotImplementedError

    @abstractmethod
    def count(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def save(self, client : Client) -> Client:
        raise NotImplementedError

    @abstractmethod
    def delete(self, client_id : UUID) -> None:
        raise NotImplementedError
