from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from src.model.remittance import RemittanceStatus, AllowedCoins
from src.validator.iban_validator import is_valid_iban 


class CreateRemittance(BaseModel):
    client_id: UUID
    amount: Decimal
    source_coin: AllowedCoins
    target_coin: AllowedCoins
    recipient_name: str
    recipient_account_iban: str

    @field_validator('recipient_name', 'recipient_account_iban', mode='after')
    @classmethod
    def validate_not_blank(cls, value: str):
        if not value or value.strip() == '':
            raise ValueError("Este campo não pode estar vazio")

        return value

    @field_validator('recipient_account_iban', mode='after')
    @classmethod
    def validate_iban(cls, iban : str):

        if not is_valid_iban(iban):
            raise ValueError("Iban inválido, use um iban válido")

        return iban

class RemittanceOut(BaseModel):
    """DTO de saída: o que a API expõe sobre uma Remittance."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    service_fee_rate: Decimal
    amount: Decimal
    amount_converted: Decimal
    source_coin: AllowedCoins
    target_coin: AllowedCoins
    service_fee_amount: Decimal
    exchange_rate: Decimal
    recipient_name: str
    recipient_account_iban: str
    status: RemittanceStatus
    created_at: datetime
    updated_at: datetime | None
