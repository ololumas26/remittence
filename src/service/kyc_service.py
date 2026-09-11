from datetime import date
from uuid import UUID

from src.model.repo.document_repo import DocumentRepository
from src.model.document import Document, DocumentType, DocumentStatus
from src.service.age_calculator import get_current_date
from src.dto.kyc_dto import KycStatus, KycStatusOut, KycDocumentSummaryOut


# Documentos que servem como identificação pessoal — qualquer um destes, aprovado e
# ainda válido, conta pra verificação de KYC. Isto é uma regra do domínio de KYC em
# si (não de remessas): RemittanceService só consome KycService.is_verified(), não
# decide sozinho o que conta como documento válido.
PERSONAL_DOCUMENT_TYPES = (DocumentType.BI, DocumentType.PASSAPORTE, DocumentType.TITULO_RESIDENCIA)

# TODO: exigir também um comprovativo de morada aprovado (ver COMPROVATIVO_MORADA)
# quando a questão da submissão desse documento for melhorada — o mesmo TODO já
# existia em RemittanceService antes desta função ser extraída para aqui.


class KycService:

    def __init__(self, document_repository: DocumentRepository):
        self.document_repo = document_repository

    def is_verified(self, client_id: UUID) -> bool:
        """Único critério que bloqueia/desbloqueia o envio de remessas — ver
        RemittanceService._ensure_client_is_verified, que apenas chama isto."""
        documents = self.document_repo.get_by_client_id(client_id)
        return self._has_valid_personal_document(documents, get_current_date())

    def get_status(self, client_id: UUID) -> KycStatusOut:
        """Estado agregado e detalhado por documento, para a app mostrar um ecrã de
        progresso do KYC — mais granular que is_verified() (só um booleano)."""
        documents = self.document_repo.get_by_client_id(client_id)
        today = get_current_date()

        personal_documents = [d for d in documents if d.document_type in PERSONAL_DOCUMENT_TYPES]

        return KycStatusOut(
            status=self._summarize(personal_documents, today),
            verified=self._has_valid_personal_document(documents, today),
            documents=[self._to_summary(document, today) for document in documents],
        )

    @staticmethod
    def _has_valid_personal_document(documents: list[Document], today: date) -> bool:
        return any(
            document.document_type in PERSONAL_DOCUMENT_TYPES
            and document.status == DocumentStatus.APPROVED
            and document.expiration_date >= today
            for document in documents
        )

    @staticmethod
    def _summarize(personal_documents: list[Document], today: date) -> KycStatus:
        if not personal_documents:
            return KycStatus.MISSING_DOCUMENTS

        if any(d.status == DocumentStatus.APPROVED and d.expiration_date >= today for d in personal_documents):
            return KycStatus.APPROVED

        if any(d.status == DocumentStatus.PENDING for d in personal_documents):
            return KycStatus.PENDING

        if any(d.status == DocumentStatus.APPROVED and d.expiration_date < today for d in personal_documents):
            return KycStatus.EXPIRED

        # Só sobra: todos os documentos de identificação submetidos foram rejeitados.
        return KycStatus.REJECTED

    @staticmethod
    def _to_summary(document: Document, today: date) -> KycDocumentSummaryOut:
        return KycDocumentSummaryOut(
            id=document.id,
            document_type=document.document_type,
            status=document.status,
            expiration_date=document.expiration_date,
            is_valid=document.status == DocumentStatus.APPROVED and document.expiration_date >= today,
        )
