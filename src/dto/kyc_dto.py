from enum import Enum
from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.model.document import DocumentType, DocumentStatus


class KycStatus(Enum):
    """Estado agregado do processo de KYC de um cliente, para a app mostrar um
    ecrã de progresso — mais granular que o booleano usado internamente para
    bloquear/desbloquear o envio de remessas (ver KycService.is_verified)."""

    MISSING_DOCUMENTS = 'missing_documents'
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    EXPIRED = 'expired'


class KycDocumentSummaryOut(BaseModel):
    """Resumo de um documento submetido pelo cliente, para a app listar o que
    já tem, o que está pendente e o que foi rejeitado sem precisar de outro
    pedido a GET /document."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_type: DocumentType
    status: DocumentStatus
    expiration_date: date
    is_valid: bool


class KycStatusOut(BaseModel):
    """Resposta de GET /client/me/kyc-status."""

    status: KycStatus
    verified: bool
    documents: list[KycDocumentSummaryOut]
