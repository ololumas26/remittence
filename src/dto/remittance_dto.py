from pydantic import BaseModel, ConfigDict
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from src.model.remittance import RemittanceStatus, AllowedCoins


class CreateRemittance(BaseModel):
    # Opcional aqui de propósito: o controller sobrepõe sempre com o client_id do utilizador
    # autenticado (create_remittance.client_id = client.id) — exigir isto no corpo do pedido só
    # fazia o pedido falhar a validação antes mesmo de chegar ao controller.
    client_id: UUID | None = None
    # Já não se recebe nome/IBAN do destinatário em texto livre aqui — o
    # cliente aponta para um Recipient já guardado (rota /recipient) e o
    # RemittanceService copia (snapshot) o nome/IBAN dele para a remessa no
    # momento da submissão.
    recipient_id: UUID
    amount: Decimal
    source_coin: AllowedCoins
    target_coin: AllowedCoins


class RemittanceOut(BaseModel):
    """DTO de saída: o que a API expõe sobre uma Remittance."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    recipient_id: UUID | None
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
