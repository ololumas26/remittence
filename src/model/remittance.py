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

    EUR = 'Euro'
    AOA = 'Kwanza Angolano'


class Remittance(SQLModel, table = True):

    __tablename__ = 'remittance'

    id : uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    client_id : uuid.UUID = Field(foreign_key='client.id', nullable=False)
    fee : Decimal = Field(nullable=False, sa_type=Numeric(10,2))
    amount : Decimal = Field(nullable=False, sa_type=Numeric(10,2))
    amount_converted : Decimal = Field(nullable=False, sa_type=Numeric(10,2))
    source_coin : AllowedCoins = Field(default=AllowedCoins.EUR, nullable=False)
    target_coin : AllowedCoins = Field(default=AllowedCoins.AOA, nullable=False)
    exchange_fee : Decimal = Field(nullable=False, sa_type=Numeric(10,2))
    exchange_rate : Decimal = Field(nullable=False, sa_type=Numeric(10,2))
    recipient_name : str = Field(nullable=False, max_length=100)
    recipient_account_iban : str = Field(nullable=False, max_length=35)
    status : RemittanceStatus = Field(default=RemittanceStatus.IN_PROGRESS, nullable=False)
    created_at : datetime = Field(default_factory=lambda : datetime.now(timezone.utc))
    updated_at : datetime = Field(nullable=True, default=None)

    client : 'Client' = Relationship(back_populates='remittance')