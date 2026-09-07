from sqlmodel import SQLModel, Field, Numeric, Relationship
from decimal import Decimal
import uuid
from datetime import datetime, timezone
from enum import Enum


class RemittanceStatus(Enum):

    IN_PROGRESS = 'In progress'
    SENT = 'Sent'
    REJECTED = 'Rejected'

class AllowedCoins(Enum):

    EUR = 'euro'
    AOA = 'aoa'


class Remittance(SQLModel, table = True):

    __tablename__ = 'remittance'

    id : uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    # Fica nullable e com ondelete='SET NULL' (ver migration) pela mesma
    # razão que recipient_id: apagar a conta de um cliente (ver "apagar
    # conta") nunca deve apagar/bloquear o histórico de remessas já feitas —
    # o histórico fica órfão (client_id fica None) mas continua a existir.
    client_id : uuid.UUID | None = Field(foreign_key='client.id', nullable=True, default=None)
    # Referência ao destinatário que originou esta remessa. Fica nullable e
    # com ondelete='SET NULL' (ver migration) porque apagar um destinatário
    # nunca deve apagar/bloquear o histórico de remessas já feitas para ele —
    # recipient_name/recipient_account_iban abaixo são a cópia (snapshot) do
    # destinatário no momento da submissão e continuam válidos mesmo que o
    # Recipient seja depois editado ou apagado.
    recipient_id : uuid.UUID | None = Field(foreign_key='recipient.id', nullable=True, default=None)
    # O pagamento que financiou esta remessa. Fica nullable e com ondelete='SET NULL' (ver
    # migration) pela mesma razão de recipient_id — o histórico da remessa não deve depender do
    # registo de pagamento continuar a existir. Preenchido pelo PaymentTransactionRepository, que
    # grava os dois numa única transação (ver PaymentService.execute_payment); a rota direta
    # POST /remittance (RemittanceService.submit sozinho) não tem pagamento associado, por isso
    # fica None nesse caminho.
    payment_id : uuid.UUID | None = Field(foreign_key='payment.id', nullable=True, default=None)
    service_fee_rate : Decimal = Field(nullable=False, sa_type=Numeric(10,2))
    amount : Decimal = Field(nullable=False, sa_type=Numeric(10,2))
    amount_converted : Decimal = Field(nullable=False, sa_type=Numeric(10,2))
    source_coin : AllowedCoins = Field(default=AllowedCoins.EUR, nullable=False)
    target_coin : AllowedCoins = Field(default=AllowedCoins.AOA, nullable=False)
    service_fee_amount : Decimal = Field(nullable=False, sa_type=Numeric(10,2))
    exchange_rate : Decimal = Field(nullable=False, sa_type=Numeric(10,2))
    recipient_name : str = Field(nullable=False, max_length=100)
    recipient_account_iban : str = Field(nullable=False, max_length=35)
    status : RemittanceStatus = Field(default=RemittanceStatus.IN_PROGRESS, nullable=False)
    ip_address : str | None = Field(nullable=True, max_length=45, default=None)
    created_at : datetime = Field(default_factory=lambda : datetime.now(timezone.utc))
    updated_at : datetime = Field(nullable=True, default=None)

    client : 'Client' = Relationship(back_populates='remittance')
    recipient : 'Recipient' = Relationship(back_populates='remittance')
    payment : 'Payment' = Relationship(back_populates='remittance')
