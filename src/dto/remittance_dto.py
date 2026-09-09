from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from src.model.remittance import RemittanceStatus, AllowedCoins
from src.model.payment_method import PaymentMethod
from src.model.payment import PaymentStatus


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
    amount: Decimal = Field(ge=50)
    source_coin: AllowedCoins
    target_coin: AllowedCoins
    # Só diz COMO o cliente quer pagar — não decide nada sozinho sobre o pagamento em si (isso
    # fica com o Payment/PaymentService, ver docs/decisions). Este DTO passa a ser recebido
    # embrulhado dentro de CreatePayment (ver payment_dto.py), não mais diretamente na rota
    # POST /remittance.
    payment_method: PaymentMethod


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
    recipient_bank_code: str | None
    status: RemittanceStatus
    created_at: datetime
    updated_at: datetime | None
    # Não vem direto do ORM (from_attributes não o preenche sozinho — Remittance não tem este
    # atributo, só payment_id) — é montado à parte pelo controller, com
    # RemittanceService.get_payment_status(), sempre que há um pagamento associado. É o que o
    # frontend faz polling (GET /remittance/{id}) para saber quando um pagamento assíncrono (ex:
    # MB WAY) passou de "Pending" a "Succeeded"/"Failed" — ver enviando.tsx no frontend.
    payment_status: PaymentStatus | None = None
    # Só preenchido para pagamentos que precisam que o cliente confirme fora da app (hoje só MB
    # WAY, via Checkout Session) — o URL da página hospedada da Stripe. Também montado à parte
    # pelo controller, a partir do que PaymentService.execute_payment devolve; None nos outros
    # métodos e para remessas já existentes lidas via GET /remittance/{id}.
    payment_redirect_url: str | None = None
