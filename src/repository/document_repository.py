from src.model.repo.document_repo import DocumentRepository
from sqlmodel import Session, select
from src.model.document import Document


class SqlDocumentRepository():

    def __init__(self, db : Session):
        self.db = db

    def get_by_document_number(self, document_number : str):
        return self.db.exec(select(Document).where(Document.document_number == document_number)).first()

    def save(self, document : Document):

        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        return document
