from supabase import Client as SupabaseClient, AuthWeakPasswordError
from supabase_auth.errors import AuthApiError
from supabase_auth.types import User

from src.dto.auth_dto import SignUp, Login, TokenOut
from src.dto.client_dto import CreateClient
from src.service.client_service import ClientService
from src.exception.exceptions import AuthenticationError


class AuthService:
    """
    Fina camada sobre o Supabase Auth: não reimplementamos sign up/login/hash
    de password, só traduzimos os pedidos/respostas para o formato da nossa
    API e mapeamos falhas do Supabase para as nossas exceções de domínio.

    O signup também orquestra a criação do perfil de KYC (ClientService),
    para o cliente ficar com conta + perfil num único pedido.
    """

    def __init__(self, supabase_client: SupabaseClient, client_service: ClientService):
        self.supabase = supabase_client
        self.client_service = client_service

    def sign_up(self, sign_up: SignUp) -> TokenOut:

        create_client = CreateClient(**sign_up.model_dump(exclude={"password"}))

        # 1. Elegibilidade primeiro (email livre, idade mínima) — se falhar,
        # nunca chegamos a criar a conta no Supabase.
        self.client_service.ensure_eligible(create_client)

        # 2. Conta no Supabase.
        try:
            response = self.supabase.auth.sign_up({
                "email": sign_up.email,
                "password": sign_up.password,
            })
        except AuthWeakPasswordError:
            raise AuthenticationError(
                "A palavra-passe deve ter uma letra maiúscula, uma letra minúscula, "
                "um número e um caracter especial, com pelo menos 8 caracteres"
            )
        except AuthApiError as error:
            raise AuthenticationError(str(error))

        if not response.user:
            raise AuthenticationError("Não foi possível criar a conta")

        # 3. Perfil de KYC, já ligado à conta acabada de criar.
        self.client_service.create(create_client, auth_user_id=response.user.id)

        # Se a confirmação de email estiver ativa no projeto Supabase, a conta
        # e o perfil já existem, mas ainda não vem sessão até o email ser
        # confirmado.
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
