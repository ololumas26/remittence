from sqlmodel import SQLModel, Field, Numeric, Relationship
from decimal import Decimal
import uuid
from datetime import datetime, timezone
from enum import Enum

from src.model.payment_method import PaymentMethod


class PaymentStatus(Enum):

    PENDING = 'Pending'
    SUCCEEDED = 'Succeeded'
    FAILED = 'Failed'


class Payment(SQLModel, table = True):

    __tablename__ = 'payment'

    id : uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    # Fica nullable e com ondelete='SET NULL' (ver migration), a mesma razão de client_id em
    # Remittance: apagar a conta de um cliente (ver "apagar conta") nunca deve apagar/bloquear o
    # histórico de pagamentos já feitos.
    client_id : uuid.UUID | None = Field(foreign_key='client.id', nullable=True, default=None)
    method : PaymentMethod = Field(nullable=False)
    status : PaymentStatus = Field(default=PaymentStatus.PENDING, nullable=False)
    # Sempre em euros — os três métodos disponíveis (MB WAY, Multibanco, cartão) só existem do
    # lado português da remessa (ver PAYMENT_METHOD_LABELS no frontend); não há por agora um
    # campo de moeda, tal como amount_converted/target_coin em Remittance não têm equivalente
    # aqui — a conversão é uma preocupação da remessa, não do pagamento que a financia.
    amount : Decimal = Field(nullable=False, sa_type=Numeric(10, 2))
    # ID/referência devolvida pelo processador (Stripe, MB WAY, referência Multibanco) — nullable
    # porque nem todos os métodos a têm de imediato, e o PaymentService.execute_payment ainda é
    # um stub que nem chega a chamar um processador real (ver TODOs nesse ficheiro).
    provider_reference : str | None = Field(nullable=True, max_length=100, default=None)
    # Só preenchido quando status == FAILED — a mensagem devolvida pelo processador ou pela
    # validação local, para dar suporte a quem for investigar um pagamento que não passou.
    failure_reason : str | None = Field(nullable=True, max_length=255, default=None)
    created_at : datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at : datetime | None = Field(nullable=True, default=None)

    client : 'Client' = Relationship(back_populates='payment')
    remittance : list['Remittance'] = Relationship(back_populates='payment')
