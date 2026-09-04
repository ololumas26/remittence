from src.model.repo.document_repo import DocumentRepository
from src.model.repo.client_repo import ClientRepository
from src.dto.document_dto import CreateDocument, UpdateDocument
from src.dto.filter import DocumentFilterParams
from src.model.document import Document, DocumentStatus
from src.service.age_calculator import get_current_date
from src.exception.exceptions import (
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
    ExpiredDocumentError,
    DocumentNotEditableError,
    DocumentNotDeletableError,
    InvalidDocumentStatusError,
    InvalidIdentifierError,
)
from src.external.service.file_storage_service import FileStorageService
from fastapi import UploadFile
from uuid import UUID
from datetime import datetime, timezone


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

        return self.document_repo.save(document)

    async def update(self, document_id : str, update_document : UpdateDocument, file : UploadFile) -> Document:

        document = self._get_or_raise(document_id)

        if not document.is_expired and document.status != DocumentStatus.REJECTED:
            raise DocumentNotEditableError("Só é possível atualizar documentos expirados ou rejeitados")

        changes = update_document.model_dump(exclude_unset=True)

        new_number = changes.get('document_number')
        if new_number and new_number != document.document_number:
            has_document = self.document_repo.get_by_document_number(new_number)
            if has_document and has_document.id != document.id:
                raise ResourceAlreadyExistsError("Já existe um documento submetido com esse número")

        new_expiration_date = changes.get('expiration_date', document.expiration_date)
        if new_expiration_date < get_current_date():
            raise ExpiredDocumentError("O documento submetido já está expirado")

        old_file_path = document.file_path
        new_file_path = await self.file_storage_service.execute(file, document.client_id)

        for key, value in changes.items():
            if value is not None:
                setattr(document, key, value)

        document.file_path = new_file_path
        document.status = DocumentStatus.PENDING
        document.is_expired = False
        document.updated_at = datetime.now(timezone.utc)

        updated_document = self.document_repo.save(document)

        if old_file_path:
            self.file_storage_service.delete_previous(old_file_path)

        return updated_document

    def delete(self, document_id : str) -> None:

        document = self._get_or_raise(document_id)

        if document.status != DocumentStatus.PENDING:
            raise DocumentNotDeletableError("Só é possível apagar documentos ainda pendentes de avaliação")

        self.document_repo.delete(document)

        if document.file_path:
            self.file_storage_service.delete_previous(document.file_path)


    def _transition_status(self, document_id : str, new_status : DocumentStatus) -> Document:

        document = self._get_or_raise(document_id)

        message = {
            DocumentStatus.APPROVED : 'aprovado',
            DocumentStatus.REJECTED : 'rejeitado',
        }

        if document.status != DocumentStatus.PENDING:
            raise InvalidDocumentStatusError(
                f"Só é possível marcar como {message[new_status]} um documento pendente "
                f"(estado atual: {document.status.value})"
            )

        document.status = new_status
        document.updated_at = datetime.now(timezone.utc)

        return document


    def approve(self, document_id : str) -> Document:

        document = self._transition_status(document_id, DocumentStatus.APPROVED)
        return self.document_repo.save(document)


    def reject(self, document_id : str) -> Document:

        document = self._transition_status(document_id, DocumentStatus.REJECTED)
        return self.document_repo.save(document)

    def get_by_id(self, document_id : str) -> Document:
        return self._get_or_raise(document_id)

    def get_all(self, filter : DocumentFilterParams):
        documents = self.document_repo.get_all(
            limit=filter.limit,
            offset=filter.offset,
            order_by=filter.order_by,
            client_id=filter.client_id,
        )
        total = self.document_repo.count(client_id=filter.client_id)

        return documents, total

    def _get_or_raise(self, document_id : str) -> Document:
        document = self.document_repo.get_by_id(self._parse_id(document_id))

        if not document:
            raise ResourceNotFoundError(f"Documento com id {document_id} não encontrado")

        return document

    @staticmethod
    def _parse_id(document_id : str) -> UUID:
        try:
            return UUID(str(document_id))
        except (ValueError, AttributeError, TypeError):
            raise InvalidIdentifierError(f"'{document_id}' não é um identificador válido")
