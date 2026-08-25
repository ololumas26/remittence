from abc import ABC, abstractmethod
from src.model.remittance import Remittance


class RemittanceRepository(ABC):

    @abstractmethod
    def save(self, remittance : Remittance) -> Remittance:
        raise NotImplementedError
    