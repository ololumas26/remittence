from sqlmodel import SQLModel, Field, Relationship, Text
import uuid
from enum import Enum
from datetime import date, datetime, timezone

class DocumentType(Enum):

    PASSAPORTE = 'Passaporte'
    TITULO_RESIDENCIA = 'Titulo de residencia'
    COMPROVATIVO_MORADA = 'Comprovativo de morada'
    BI = "Bilhete de identidade"

class DocumentStatus(Enum):

    PENDING = 'pendent'
    APPROVED = 'approved'
    REJECTED = 'rejected'


class Document(SQLModel, table = True):

    __tablename__ = 'document'

    id : uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    client_id : uuid.UUID = Field(foreign_key='client.id', nullable=False)
    document_number : str = Field(nullable=False, max_length=15, unique=True)
    is_expired : bool = Field(default=False)
    document_type : DocumentType = Field(nullable=False)
    expiration_date : date = Field(nullable=False)
    file_path : str = Field(sa_type=Text, nullable=True)
    status : DocumentStatus = Field(default=DocumentStatus.PENDING)
    note : str | None = Field(nullable=True, max_length=500, default=None)
    created_at : datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at : datetime = Field(nullable=True, default=None)

    client : 'Client' = Relationship(back_populates='document')