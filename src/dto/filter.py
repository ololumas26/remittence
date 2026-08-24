from pydantic import BaseModel, Field
from typing import Literal
from uuid import UUID


class FilterParams(BaseModel):
    limit: int = Field(10, gt=0, le=100)
    offset: int = Field(0, ge=0)
    order_by: Literal["created_at", "updated_at"] = "created_at"


class DocumentFilterParams(FilterParams):
    client_id: UUID | None = None
