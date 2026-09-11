from abc import ABC, abstractmethod
from src.model.payment import Payment, PaymentStatus
from uuid import UUID


class PaymentRepository(ABC):

    @abstractmethod
    def get_by_id(self, payment_id : UUID) -> Payment | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, payment : Payment) -> Payment:
        raise NotImplementedError

    @abstractmethod
    def get_by_provider_reference(self, provider_reference : str) -> Payment | None:
        raise NotImplementedError

    @abstractmethod
    def get_all(
        self, limit : int, offset : int, order_by : str, client_id : UUID | None = None,
        status : PaymentStatus | None = None,
    ) -> list[Payment]:
        raise NotImplementedError

    @abstractmethod
    def count(
        self, client_id : UUID | None = None, status : PaymentStatus | None = None,
    ) -> int:
        raise NotImplementedError
