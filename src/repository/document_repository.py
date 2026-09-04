from src.model.repo.document_repo import DocumentRepository
from sqlmodel import Session, select, func
from src.model.document import Document
from uuid import UUID


class SqlDocumentRepository():

    def __init__(self, db : Session):
        self.db = db

    def get_by_document_number(self, document_number : str):
        return self.db.exec(select(Document).where(Document.document_number == document_number)).first()

    def get_by_id(self, document_id : str):
        return self.db.exec(select(Document).where(Document.id == document_id)).first()

    def get_all(self, limit : int, offset : int, order_by : str, client_id : UUID | None = None):
        order_column = getattr(Document, order_by)
        statement = select(Document)

        if client_id:
            statement = statement.where(Document.client_id == client_id)

        # .desc() sempre — quem lista remessas/documentos/destinatários quer sempre o mais
        # recente primeiro, nunca o mais antigo.
        statement = statement.order_by(order_column.desc()).limit(limit).offset(offset)
        return self.db.exec(statement).all()

    def count(self, client_id : UUID | None = None) -> int:
        statement = select(func.count()).select_from(Document)

        if client_id:
            statement = statement.where(Document.client_id == client_id)

        return self.db.exec(statement).one()

    def get_by_client_id(self, client_id : UUID):
        return self.db.exec(select(Document).where(Document.client_id == client_id)).all()

    def save(self, document : Document):

        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        return document

    def delete(self, document : Document):
        self.db.delete(document)
        self.db.commit()
