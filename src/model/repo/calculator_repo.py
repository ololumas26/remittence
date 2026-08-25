from abc import ABC, abstractmethod
from decimal import Decimal


class CalculatorRepository(ABC):

    @abstractmethod
    def calculate(self, amount : Decimal, exchange_rate : Decimal):
        raise NotImplementedError
