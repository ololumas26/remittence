import logging

from src.model.repo.document_repo import DocumentRepository
from src.model.repo.client_repo import ClientRepository
from src.dto.document_dto import CreateDocument, UpdateDocument
from src.dto.filter import DocumentFilterParams
from src.model.document import Document, DocumentStatus
from src.service.age_calculator import get_current_date
from src.service.notification_service import NotificationService
from src.service.document_email_template import (
    document_approved_subject,
    document_rejected_subject,
    render_document_approved_email,
    render_document_rejected_email,
)
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
from src.external.service.email_service import EmailService
from fastapi import UploadFile
from uuid import UUID
from datetime import datetime, timezone

logger = logging.getLogger("remittance")


class DocumentService:

    def __init__(self, document_repository : DocumentRepository, client_repository : ClientRepository,
                 file_storage_service : FileStorageService, email_service : EmailService):
        self.document_repo = document_repository
        self.client_repo = client_repository
        self.file_storage_service = file_storage_service
        self.email_service = email_service

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
        notification = NotificationService.for_document_approved(document)
        saved_document = self.document_repo.save_with_notification(document, notification)
        self._send_approved_email(saved_document)
        return saved_document


    def reject(self, document_id : str, note : str) -> Document:

        document = self._transition_status(document_id, DocumentStatus.REJECTED)
        document.note = note
        notification = NotificationService.for_document_rejected(document, note)
        saved_document = self.document_repo.save_with_notification(document, notification)
        self._send_rejected_email(saved_document, note)
        return saved_document

    def _send_approved_email(self, document : Document) -> None:
        # Mesma rede de segurança de RemittanceService.send_created_email: o EmailService já não
        # levanta exceção nenhuma, mas isto garante que uma falha imprevista a MONTAR o email
        # nunca deixa approve() em si falhar depois de o documento já ter sido aprovado.
        try:
            client = self.client_repo.get_by_id(document.client_id)
            if not client:
                return
            subject = document_approved_subject(document)
            html = render_document_approved_email(client.name, document)
            # TODO: SUBSTITUIR DEPOIS PARA O EMAIL DO CLIENTE QUANDO JÁ ESTIVER EM PRODUÇÃO
            self.email_service.send('ololumas26@gmail.com', subject, html)
        except Exception:
            logger.exception("Falha ao preparar o email de documento aprovado para o documento %s", document.id)

    def _send_rejected_email(self, document : Document, note : str) -> None:
        try:
            client = self.client_repo.get_by_id(document.client_id)
            if not client:
                return
            subject = document_rejected_subject(document)
            html = render_document_rejected_email(client.name, document, note)
            # TODO: SUBSTITUIR DEPOIS PARA O EMAIL DO CLIENTE QUANDO JÁ ESTIVER EM PRODUÇÃO
            self.email_service.send('ololumas26@gmail.com', subject, html)
        except Exception:
            logger.exception("Falha ao preparar o email de documento rejeitado para o documento %s", document.id)

    def get_by_id(self, document_id : str) -> Document:
        return self._get_or_raise(document_id)

    def get_signed_url(self, document_id : str, expires_in : int = 300) -> str:
        document = self._get_or_raise(document_id)

        if not document.file_path:
            raise ResourceNotFoundError(f"Documento com id {document_id} não tem ficheiro associado")

        return self.file_storage_service.get_signed_url(document.file_path, expires_in)

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
