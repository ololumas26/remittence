from supabase import Client as SupabaseClient
from supabase_auth.errors import AuthApiError
from supabase_auth.types import User

from src.dto.auth_dto import SignUp, Login, TokenOut
from src.exception.exceptions import AuthenticationError


class AuthService:
    """
    Fina camada sobre o Supabase Auth: não reimplementamos sign up/login/hash
    de password, só traduzimos os pedidos/respostas para o formato da nossa
    API e mapeamos falhas do Supabase para as nossas exceções de domínio.
    """

    def __init__(self, supabase_client: SupabaseClient):
        self.supabase = supabase_client

    def sign_up(self, sign_up: SignUp) -> TokenOut:
        try:
            response = self.supabase.auth.sign_up({
                "email": sign_up.email,
                "password": sign_up.password,
            })
        except AuthApiError as error:
            raise AuthenticationError(str(error))

        # Se a confirmação de email estiver ativa no projeto Supabase, a conta
        # é criada mas não vem sessão nenhuma até o email ser confirmado.
        if not response.session:
            raise AuthenticationError(
                "Conta criada com sucesso, mas é preciso confirmar o email "
                "antes de iniciar sessão (verifica a caixa de entrada)."
            )

        return TokenOut(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
        )

    def login(self, login: Login) -> TokenOut:
        try:
            response = self.supabase.auth.sign_in_with_password({
                "email": login.email,
                "password": login.password,
            })
        except AuthApiError:
            # Mensagem genérica de propósito: não revelar se foi o email ou a
            # password que estava errada (evita confirmar quais emails existem).
            raise AuthenticationError("Email ou password incorretos")

        return TokenOut(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
        )

    def refresh(self, refresh_token: str) -> TokenOut:
        try:
            response = self.supabase.auth.refresh_session(refresh_token)
        except AuthApiError:
            raise AuthenticationError("Refresh token inválido ou expirado")

        return TokenOut(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
        )

    def get_current_user(self, access_token: str) -> User:
        try:
            response = self.supabase.auth.get_user(access_token)
        except AuthApiError:
            raise AuthenticationError("Token inválido ou expirado")

        if not response or not response.user:
            raise AuthenticationError("Token inválido ou expirado")

        return response.user
