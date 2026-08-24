from src.model.repo.document_repo import DocumentRepository
from src.model.repo.client_repo import ClientRepository
from src.dto.document_dto import CreateDocument
from src.model.document import Document
from src.service.age_calculator import get_current_date
from src.exception.exceptions import (
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
    ExpiredDocumentError,
)
from src.external.service.file_storage_service import FileStorageService
from fastapi import UploadFile


class DocumentService:

    def __init__(self, document_repository : DocumentRepository, client_repository : ClientRepository,
                 file_storage_service : FileStorageService):
        self.document_repo = document_repository
        self.client_repo = client_repository
        self.file_storage_service = file_storage_service

    async def submit(self, create_document : CreateDocument, file : UploadFile) -> Document:

        client = self.client_repo.get_by_id(create_document.client_id)

        if not client:
            raise ResourceNotFoundError(f"Cliente com id {create_document.client_id} não encontrado")

        has_document = self.document_repo.get_by_document_number(create_document.document_number)

        if has_document:
            raise ResourceAlreadyExistsError("Já existe um documento submetido com esse número")

        if create_document.expiration_date < get_current_date():
            raise ExpiredDocumentError("O documento submetido já está expirado")

        response = await self.file_storage_service.execute(file, create_document.client_id)

        document = Document(**create_document.model_dump())
        document.file_path = response

        return  self.document_repo.save(document)
