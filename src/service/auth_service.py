from supabase import Client as SupabaseClient, AuthWeakPasswordError
from supabase_auth.errors import AuthApiError
from supabase_auth.types import User
from uuid import UUID

from src.dto.auth_dto import SignUp, Login, TokenOut
from src.dto.client_dto import CreateClient
from src.service.client_service import ClientService
from src.exception.exceptions import AuthenticationError, AccountDeletionError


class AuthService:
    """
    Fina camada sobre o Supabase Auth: não reimplementamos sign up/login/hash
    de password, só traduzimos os pedidos/respostas para o formato da nossa
    API e mapeamos falhas do Supabase para as nossas exceções de domínio.

    O perfil de KYC (ClientService) só é persistido depois, quando a conta
    já tiver sessão válida — ou seja, com o email confirmado (quando essa
    confirmação está ativa no projeto Supabase). Isto evita criar um
    registo de cliente "por confirmar" que nunca chega a ser usado se a
    pessoa não confirmar o email, e evita verificar a mesma elegibilidade
    (email livre, idade mínima) duas vezes no mesmo pedido.

    Para não obrigar o cliente a preencher outra vez nome/telefone/data de
    nascimento depois de confirmar o email, esses dados (não sensíveis a
    nível de autorização — ao contrário de um "role") viajam em
    user_metadata desde o signup. get_current_client (ver
    src/controller/dependency.py) usa-os para criar o perfil
    automaticamente na primeira ação autenticada, sem pedir nada outra vez.
    """

    def __init__(
        self,
        supabase_client: SupabaseClient,
        client_service: ClientService,
        admin_client: SupabaseClient,
    ):
        self.supabase = supabase_client
        self.client_service = client_service
        # Cliente com a service_role key — só a Admin API consegue apagar
        # uma conta do Auth (delete_account), o cliente "normal" não tem
        # permissão para isso mesmo autenticado como a própria conta.
        self.admin_client = admin_client

    def sign_up(self, sign_up: SignUp) -> TokenOut:

        create_client = CreateClient(**sign_up.model_dump(exclude={"password"}))

        # Elegibilidade primeiro (email livre, idade mínima) — pré-verificação
        # rápida para não criar uma conta no Supabase para alguém que nunca
        # vai conseguir ter perfil. A verificação "a sério" (que persiste)
        # só volta a acontecer em ClientService.create() — não há dupla
        # verificação no mesmo pedido.
        self.client_service.ensure_eligible(create_client)

        try:
            response = self.supabase.auth.sign_up({
                "email": sign_up.email,
                "password": sign_up.password,
                # Guardado em user_metadata só para recuperar estes dados depois
                # da confirmação do email (ver get_current_client) — nunca é
                # usado para autorização/papéis, isso continua exclusivamente
                # em app_metadata.
                "options": {
                    "data": {
                        "name": create_client.name,
                        "phone_number": create_client.phone_number,
                        "birth_date": create_client.birth_date.isoformat(),
                    },
                },
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
        # de KYC só é criado mais tarde, já autenticado com sessão válida (a
        # primeira ação autenticada provisiona-o automaticamente — ver
        # get_current_client) — nunca aqui, com a conta ainda por confirmar.
        if not response.session:
            raise AuthenticationError(
                "Conta criada com sucesso. Confirma o teu email e depois inicia sessão."
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

    def sign_in_with_google(self, id_token: str) -> TokenOut:
        """
        Troca um ID token do Google (obtido no telemóvel, ver o botão "Continuar com Google" no
        frontend) por uma sessão Supabase. O Supabase cria a conta no Auth automaticamente da
        primeira vez (mesmo mecanismo do signup por email, só que sem password).

        Ao contrário do signup por email, o Google não dá telemóvel nem data de nascimento — e
        são obrigatórios para o perfil de KYC (Client.birth_date não é nullable). Não tentamos
        provisionar o perfil aqui: get_current_client (ver controller/dependency.py) já sabe
        devolver 404 quando a metadata não chega para isso, e é esse 404 em GET /client/me — não
        um campo à parte na resposta deste método — que o frontend usa para saber que ainda falta
        completar o perfil (ver GET /auth/me e o ecrã "completar-perfil").
        """
        try:
            response = self.supabase.auth.sign_in_with_id_token({
                "provider": "google",
                "token": id_token,
            })
        except AuthApiError as error:
            raise AuthenticationError(str(error))

        if not response.session:
            raise AuthenticationError("Não foi possível iniciar sessão com o Google")

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

    def forgot_password(self, email: str) -> None:
        """
        Envia um código de recuperação por email. Nunca propaga falhas do
        Supabase (ex: rate limit) nem revela se a conta existe — mesma
        filosofia do login (ver .login): quem chama isto não deve conseguir
        distinguir "email enviado" de "conta não existe" pela resposta.
        """
        try:
            self.supabase.auth.reset_password_for_email(email)
        except AuthApiError:
            pass

    def reset_password(self, email: str, token: str, new_password: str) -> TokenOut:
        """
        Confirma o código de recuperação (enviado por forgot_password) e
        define a nova password.

        Usa admin_client (Admin API) para definir a password, não
        supabase.auth.update_user: esse depende da sessão guardada na
        instância partilhada de supabase (ver __init__) — usar isso aqui
        arriscaria misturar sessão entre pedidos concorrentes. A Admin API
        atua diretamente sobre o id do utilizador devolvido por verify_otp,
        sem depender de nenhum estado guardado no cliente.
        """
        try:
            verify_response = self.supabase.auth.verify_otp({
                "email": email,
                "token": token,
                "type": "recovery",
            })
        except AuthApiError:
            raise AuthenticationError("Código inválido ou expirado")

        if not verify_response.user:
            raise AuthenticationError("Código inválido ou expirado")

        try:
            self.admin_client.auth.admin.update_user_by_id(
                str(verify_response.user.id),
                {"password": new_password},
            )
        except AuthWeakPasswordError:
            raise AuthenticationError(
                "A palavra-passe deve ter uma letra maiúscula, uma letra minúscula, "
                "um número e um caracter especial, com pelo menos 8 caracteres"
            )
        except AuthApiError as error:
            raise AuthenticationError(str(error))

        # Login imediato com a nova password — devolve uma sessão obtida por esta chamada (não
        # depende do estado deixado pelo verify_otp acima), para a pessoa não ter de voltar ao
        # ecrã de login depois de repor a password.
        return self.login(Login(email=email, password=new_password))

    def delete_account(self, auth_user_id: UUID) -> None:
        """
        Apaga a conta no Supabase Auth. Só a Admin API (service_role)
        consegue fazer isto — por isso usa admin_client, não supabase.

        Deve ser chamado ANTES de apagar o perfil (Client) local: enquanto a
        conta Auth existir, get_current_client (ver controller/dependency.py)
        recria automaticamente o perfil a partir do user_metadata assim que
        houver um pedido autenticado seguinte — apagar só o perfil local
        "ressuscitaria" a conta na próxima ação.
        """
        try:
            self.admin_client.auth.admin.delete_user(str(auth_user_id))
        except AuthApiError as error:
            raise AccountDeletionError(str(error))

    def get_current_user(self, access_token: str) -> User:
        try:
            response = self.supabase.auth.get_user(access_token)
        except AuthApiError:
            raise AuthenticationError("Token inválido ou expirado")

        if not response or not response.user:
            raise AuthenticationError("Token inválido ou expirado")

        return response.user
