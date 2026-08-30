from pydantic import BaseModel, field_validator
from src.validator.email_validator import is_valid_email


class SignUp(BaseModel):
    email: str
    password: str

    @field_validator('email', mode='after')
    @classmethod
    def validate_email(cls, email: str):
        if not is_valid_email(email):
            raise ValueError("Email com formato incorreto")
        return email

    @field_validator('password', mode='after')
    @classmethod
    def validate_password(cls, password: str):
        if not password or len(password) < 8:
            raise ValueError("A password deve ter pelo menos 8 caracteres")
        return password


class Login(BaseModel):
    email: str
    password: str


class RefreshToken(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
