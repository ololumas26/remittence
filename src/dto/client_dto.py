from pydantic import BaseModel, ConfigDict, field_validator, ValidationInfo
from datetime import date, datetime
from uuid import UUID
from src.validator.email_validator import is_valid_email


to_portuguese = {
    'name' :'Nome',
    'phone_number' : 'Telemóvel',
    'birth_date' : 'Data de nascimento',
    'email': 'Email'
}


class ClientBase(BaseModel):
    name : str
    email : str
    phone_number : str


class CreateClient(ClientBase):

    birth_date : date

    @field_validator('name','email','birth_date', mode='after')
    @classmethod
    def validate_fields(cls, value : str, field : ValidationInfo):

        if field.field_name != 'birth_date':
            if not value or value.strip() == '':
                raise ValueError(f"O campo '{to_portuguese[field.field_name]}' não pode estar vazio")

        return value

    @field_validator('email', mode='after')
    @classmethod
    def validate_email(cls, email : str):

        if not is_valid_email(email):
            raise ValueError("Email com formato incorreto")

        return email


class UpdateClient(ClientBase):
    birth_date : date | None = None
    name : str | None
    email : str | None
    phone_number : str | None

class ClientOut(BaseModel):
    """DTO de saída: define o que a API expõe sobre um Client,
    independente dos detalhes internos do modelo persistido."""

    model_config = ConfigDict(from_attributes=True)

    id : UUID
    name : str
    email : str
    phone_number : str | None
    birth_date : date
    image_url : str | None
    created_at : datetime
    updated_at : datetime | None
