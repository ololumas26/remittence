from pydantic import BaseModel, field_validator
from src.validator.email_validator import is_valid_email
from src.dto.client_dto import CreateClient


class SignUp(CreateClient):
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


class ForgotPassword(BaseModel):
    email: str

    @field_validator('email', mode='after')
    @classmethod
    def validate_email(cls, email: str):
        if not is_valid_email(email):
            raise ValueError("Email com formato incorreto")
        return email


class ResetPassword(BaseModel):
    email: str
    # Código de 6 dígitos enviado por email (ver AuthService.forgot_password) — não confundir
    # com um access/refresh token, apesar do nome do campo no Supabase ("token") ser o mesmo.
    token: str
    new_password: str

    @field_validator('email', mode='after')
    @classmethod
    def validate_email(cls, email: str):
        if not is_valid_email(email):
            raise ValueError("Email com formato incorreto")
        return email

    @field_validator('new_password', mode='after')
    @classmethod
    def validate_new_password(cls, password: str):
        if not password or len(password) < 8:
            raise ValueError("A password deve ter pelo menos 8 caracteres")
        return password


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class GoogleSignIn(BaseModel):
    # ID token OIDC devolvido pelo Google ao cliente (ver AuthService.sign_in_with_google) — não
    # confundir com o access_token da nossa própria sessão.
    id_token: str


class SessionIdentityOut(BaseModel):
    """
    Identidade básica da conta Auth autenticada — não o perfil de KYC (para isso, GET /client/me).
    Usada quando GET /client/me dá 404 (perfil ainda por completar, tipicamente depois de um
    login com Google — ver AuthService.sign_in_with_google): dá ao frontend o email/nome que o
    provider já forneceu, para não voltar a pedi-los no ecrã de completar perfil.
    """

    email: str
    name: str | None = None
