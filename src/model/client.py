from sqlmodel import SQLModel, Relationship, Field, DateTime
import uuid
from datetime import datetime, timezone, date



class Client(SQLModel, table = True):

    __tablename__ = 'client'

    id : uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    name : str = Field(nullable=False, max_length=100)
    email : str = Field(nullable=False, unique=True, index=True)
    phone_number : str = Field(nullable=True, max_digits=12, default=None)
    birth_date : date = Field(nullable=False)
    # Liga este cliente ao utilizador correspondente no Supabase Auth. Fica
    # nullable para não partir dados já existentes sem conta associada, mas
    # o fluxo de criação (ClientService.create) passa sempre a preenchê-lo.
    auth_user_id : uuid.UUID | None = Field(nullable=True, unique=True, index=True, default=None)
    # URL pública da foto de perfil no Supabase Storage (bucket separado dos documentos de KYC —
    # ver get_client_service). Nullable: sem foto, o frontend mostra as iniciais do nome em vez
    # disto (ver ClientOut.image_url e derive-initials.ts no frontend).
    image_url : str | None = Field(nullable=True, default=None)
    created_at : datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at : datetime = Field(default=None, nullable=True, sa_type=DateTime)

    document : list['Document'] = Relationship(back_populates='client', cascade_delete=True)
    remittance : list['Remittance'] = Relationship(back_populates='client')
    payment : list['Payment'] = Relationship(back_populates='client')
    recipient : list['Recipient'] = Relationship(back_populates='client', cascade_delete=True)
