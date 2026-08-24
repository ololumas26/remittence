from abc import ABC, abstractmethod
from src.model.document import Document
from uuid import UUID


class DocumentRepository(ABC):

    @abstractmethod
    def get_by_document_number(self, document_number : str) -> Document | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, document_id : UUID) -> Document | None:
        raise NotImplementedError

    @abstractmethod
    def get_all(self, limit : int, offset : int, order_by : str, client_id : UUID | None = None) -> list[Document]:
        raise NotImplementedError

    @abstractmethod
    def count(self, client_id : UUID | None = None) -> int:
        raise NotImplementedError

    @abstractmethod
    def save(self, document : Document) -> Document:
        raise NotImplementedError

    @abstractmethod
    def delete(self, document : Document) -> None:
        raise NotImplementedError
