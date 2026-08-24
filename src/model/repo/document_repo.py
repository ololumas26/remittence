from abc import ABC, abstractmethod
from src.model.document import Document


class DocumentRepository(ABC):

    @abstractmethod
    def get_by_document_number(self, document_number : str) -> Document | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, document : Document) -> Document:
        raise NotImplementedError
