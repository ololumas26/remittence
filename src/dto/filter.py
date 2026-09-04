from pydantic import BaseModel, Field, model_validator
from typing import Literal
from uuid import UUID
from datetime import date

from src.model.remittance import RemittanceStatus


class FilterParams(BaseModel):
    limit: int = Field(10, gt=0, le=100)
    offset: int = Field(0, ge=0)
    order_by: Literal["created_at", "updated_at"] = "created_at"


class DocumentFilterParams(FilterParams):
    client_id: UUID | None = None


class RecipientFilterParams(FilterParams):
    client_id: UUID | None = None
    # "last_sent_at": ordena pela remessa mais recente enviada a cada destinatário (não por
    # quando o destinatário foi criado) — usado pela Home para mostrar sempre as últimas pessoas
    # a quem foram enviados valores primeiro. Destinatários sem nenhuma remessa ainda ficam no
    # fim, ordenados por created_at (ver SqlRecipientRepository.get_all).
    order_by: Literal["created_at", "updated_at", "last_sent_at"] = "created_at"


class RemittanceFilterParams(FilterParams):
    client_id: UUID | None = None
    status: RemittanceStatus | None = None
    # Intervalo de datas sobre created_at (inclusive dos dois lados). Datas, não
    # datetimes — quem está a filtrar não quer saber da hora exata, só do dia.
    created_from: date | None = None
    created_to: date | None = None

    @model_validator(mode='after')
    def validate_date_range(self):
        if self.created_from and self.created_to and self.created_from > self.created_to:
            raise ValueError("'created_from' não pode ser posterior a 'created_to'")

        return self
