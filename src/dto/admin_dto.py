"""
DTOs de saída só para as rotas de admin/staff (GET /remittance/admin/all,
GET /payment/admin/all — ver require_staff em src/security/dependencies.py).

Ficam à parte de remittance_dto.py/payment_dto.py (que servem a app do cliente) porque expõem
mais do que um cliente deveria ver sobre si próprio (ex: payment_id em bruto) e porque juntam
dados de mais que uma entidade numa só resposta (remessa + quem a pediu + o pagamento que a
financiou), o que a app do cliente nunca precisa de fazer numa única chamada.
"""

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from src.dto.client_dto import ClientOut
from src.model.remittance import RemittanceStatus, AllowedCoins
from src.model.payment import PaymentStatus
from src.model.payment_method import PaymentMethod


class PaymentSummaryOut(BaseModel):
    """O pagamento tal como interessa ver a partir de uma remessa — não o payment completo
    (sem provider_reference/failure_reason, que só interessam ao abrir o pagamento em si)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    method: PaymentMethod
    status: PaymentStatus
    amount: Decimal


class RemittanceSummaryOut(BaseModel):
    """A remessa tal como interessa ver a partir de um pagamento — só o suficiente para saber
    para quem/quanto/se já foi enviada, sem repetir todos os campos de RemittanceAdminOut."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recipient_name: str
    amount_converted: Decimal
    target_coin: AllowedCoins
    status: RemittanceStatus


class RemittanceAdminOut(BaseModel):
    """Uma remessa para a dashboard de admin: os mesmos dados que RemittanceOut expõe ao
    cliente, mais o payment_id em bruto (RemittanceOut não o expõe — não é da conta do cliente) e
    um resumo do cliente/pagamento associados, para o admin não precisar de um pedido por remessa
    só para saber quem a pediu e se já foi paga."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID | None
    recipient_id: UUID | None
    payment_id: UUID | None
    service_fee_rate: Decimal
    amount: Decimal
    amount_converted: Decimal
    source_coin: AllowedCoins
    target_coin: AllowedCoins
    service_fee_amount: Decimal
    exchange_rate: Decimal
    recipient_name: str
    recipient_account_iban: str
    recipient_bank_code: str | None
    status: RemittanceStatus
    note: str | None
    created_at: datetime
    updated_at: datetime | None
    # Preenchidos automaticamente pelo from_attributes a partir de Remittance.client/.payment
    # (Relationship do SQLModel) — nenhum dos dois precisa de ser montado à mão no controller.
    client: ClientOut | None = None
    payment: PaymentSummaryOut | None = None


class PaymentAdminOut(BaseModel):
    """Um pagamento para a dashboard de admin: os campos do Payment, mais quem o fez e a(s)
    remessa(s) que financiou (Payment.remittance é uma Relationship de um-para-muitos — ver
    comentário no model — por isso é sempre uma lista, tipicamente com um único elemento)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID | None
    method: PaymentMethod
    status: PaymentStatus
    amount: Decimal
    provider_reference: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime | None
    client: ClientOut | None = None
    remittances: list[RemittanceSummaryOut] = []
