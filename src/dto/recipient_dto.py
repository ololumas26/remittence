from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from uuid import UUID

from src.validator.iban_validator import is_valid_iban


class CreateRecipient(BaseModel):
    # Opcional aqui de propósito: o controller sobrepõe sempre com o client_id do utilizador
    # autenticado (create_recipient.client_id = client.id) — exigir isto no corpo do pedido só
    # fazia o pedido falhar a validação antes mesmo de chegar ao controller.
    client_id: UUID | None = None
    full_name: str
    account_iban: str
    location: str | None = None
    relationship: str | None = None

    @field_validator('full_name', 'account_iban', mode='after')
    @classmethod
    def validate_not_blank(cls, value: str):
        if not value or value.strip() == '':
            raise ValueError("Este campo não pode estar vazio")

        return value

    @field_validator('account_iban', mode='after')
    @classmethod
    def validate_iban(cls, iban: str):

        if not is_valid_iban(iban):
            raise ValueError("Iban inválido, use um iban válido")

        return iban


class UpdateRecipient(BaseModel):
    full_name: str | None = None
    account_iban: str | None = None
    location: str | None = None
    relationship: str | None = None

    @field_validator('full_name', 'account_iban', mode='after')
    @classmethod
    def validate_not_blank(cls, value: str | None):
        if value is not None and value.strip() == '':
            raise ValueError("Este campo não pode estar vazio")

        return value

    @field_validator('account_iban', mode='after')
    @classmethod
    def validate_iban(cls, iban: str | None):

        if iban is not None and not is_valid_iban(iban):
            raise ValueError("Iban inválido, use um iban válido")

        return iban


class RecipientOut(BaseModel):
    """DTO de saída: o que a API expõe sobre um Recipient."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    full_name: str
    account_iban: str
    location: str | None
    relationship: str | None
    created_at: datetime
    updated_at: datetime | None
