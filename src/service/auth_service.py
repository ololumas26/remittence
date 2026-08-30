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

    O perfil de KYC (ClientService) só é criado depois, através de
    POST /client/, quando a conta já tiver sessão válida — ou seja, com o
    email confirmado (quando essa confirmação está ativa no projeto
    Supabase). Isto evita criar um registo de cliente "por confirmar" que
    nunca chega a ser usado se a pessoa não confirmar o email, e evita
    verificar a mesma elegibilidade (email livre, idade mínima) duas vezes
    no mesmo pedido.
    """

    def __init__(self, supabase_client: SupabaseClient, client_service: ClientService):
        self.supabase = supabase_client
        self.client_service = client_service

    def sign_up(self, sign_up: SignUp) -> TokenOut:

        create_client = CreateClient(**sign_up.model_dump(exclude={"password"}))

        # Elegibilidade primeiro (email livre, idade mínima) — pré-verificação
        # rápida para não criar uma conta no Supabase para alguém que nunca
        # vai conseguir ter perfil. A verificação "a sério" (que persiste)
        # só volta a acontecer em ClientService.create(), chamado a partir de
        # POST /client/ — não há dupla verificação no mesmo pedido.
        self.client_service.ensure_eligible(create_client)

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

        # Se a confirmação de email estiver ativa no projeto Supabase, a conta
        # existe mas ainda não há sessão até o email ser confirmado. O perfil
        # de KYC só é criado mais tarde (POST /client/, já autenticado com
        # sessão válida) — nunca aqui, com a conta ainda por confirmar.
        if not response.session:
            raise AuthenticationError(
                "Conta criada com sucesso. Confirma o teu email e depois inicia "
                "sessão para completares o teu perfil (POST /client/)."
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
