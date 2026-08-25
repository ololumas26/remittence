from abc import ABC, abstractmethod
from src.model.remittance import Remittance
from uuid import UUID


class RemittanceRepository(ABC):

    @abstractmethod
    def get_by_id(self, remittance_id : UUID) -> Remittance | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, remittance : Remittance) -> Remittance:
        raise NotImplementedError
