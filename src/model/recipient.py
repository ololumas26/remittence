from sqlmodel import SQLModel, Field, Relationship
import uuid
from datetime import datetime, timezone


class Recipient(SQLModel, table = True):

    __tablename__ = 'recipient'

    id : uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    client_id : uuid.UUID = Field(foreign_key='client.id', nullable=False)
    full_name : str = Field(nullable=False, max_length=100)
    account_iban : str = Field(nullable=False, max_length=35)
    bank_code : str | None = Field(nullable=True, max_length=4, default=None)
    location : str | None = Field(nullable=True, max_length=120, default=None)
    # Etiqueta livre ("Mãe", "Irmão", ...) usada só para apresentação na app — não
    # entra em nenhuma regra de negócio nem validação, ao contrário de full_name/account_iban.
    relationship : str | None = Field(nullable=True, max_length=60, default=None)
    created_at : datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at : datetime = Field(nullable=True, default=None)

    client : 'Client' = Relationship(back_populates='recipient')
    remittance : list['Remittance'] = Relationship(back_populates='recipient')
