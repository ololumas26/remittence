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
    created_at : datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at : datetime = Field(default=None, nullable=True, sa_type=DateTime)