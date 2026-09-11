from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import date, datetime
from uuid import UUID


from src.model.document import DocumentType, DocumentStatus


class CreateDocument(BaseModel):
    client_id: UUID
    document_type: DocumentType
    document_number: str
    expiration_date: date

    @field_validator('document_number', mode='after')
    @classmethod
    def validate_not_blank(cls, value: str):
        if not value or value.strip() == '':
            raise ValueError("Este campo não pode estar vazio")

        return value


class UpdateDocument(BaseModel):
    document_type: DocumentType | None = None
    document_number: str | None = None
    expiration_date: date | None = None

    @field_validator('document_number', mode='after')
    @classmethod
    def validate_not_blank(cls, value: str | None):
        if value is not None and value.strip() == '':
            raise ValueError("Este campo não pode estar vazio")

        return value


class RejectDocument(BaseModel):
    """Corpo de PATCH /document/{id}/reject — o staff tem sempre de justificar a rejeição
    (ver DocumentService.reject)."""

    note: str = Field(min_length=3, max_length=500)

    @field_validator('note', mode='after')
    @classmethod
    def validate_not_blank(cls, value: str):
        # min_length sozinho não chega: "   " tem 3 caracteres mas não é uma justificação —
        # mesmo problema que document_number já trata em CreateDocument/UpdateDocument acima.
        stripped = value.strip()
        if stripped == '':
            raise ValueError("Este campo não pode estar vazio")

        return stripped


class DocumentOut(BaseModel):
    """DTO de saída: o que a API expõe sobre um Document."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    document_type: DocumentType
    document_number: str
    expiration_date: date
    is_expired: bool
    status: DocumentStatus
    file_path: str | None
    note: str | None
    created_at: datetime
    updated_at: datetime | None
