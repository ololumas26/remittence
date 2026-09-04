from enum import Enum
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.database.db import session_DP
from src.repository.client_repository import SqlClientRepository
from src.service.client_service import ClientService
from src.service.auth_service import AuthService
from src.supabase.server import client, admin_client
from src.exception.exceptions import AuthenticationError, AuthorizationError


class Role(str, Enum):
    """
    Papéis aplicacionais reconhecidos pela API. Herdar de str permite comparar
    diretamente com o valor bruto guardado no app_metadata (Role.STAFF == "staff").
    """
    CLIENT = "client"
    STAFF = "staff"


def get_client_service(session : session_DP) -> ClientService:
    return ClientService(SqlClientRepository(session))


def get_auth_service(client_service : ClientService = Depends(get_client_service)) -> AuthService:
    return AuthService(client, client_service, admin_client)


# auto_error=False para nós controlarmos a resposta de erro (mantém o
# formato {data, error, message} da API em vez do 403 genérico do FastAPI
# quando o header Authorization vem em falta).
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials : Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    auth_service : AuthService = Depends(get_auth_service),
):
    """
    Valida o token Bearer e devolve o User do Supabase Auth (a conta, não o
    perfil de KYC — para isso ver get_current_client em controller/dependency.py).
    """

    if credentials is None:
        raise AuthenticationError("Token de autenticação em falta")

    return auth_service.get_current_user(credentials.credentials)


def get_user_id(user = Depends(get_current_user)) -> UUID:
    """Id da conta Supabase Auth autenticada (auth_user_id) — não confundir com Client.id."""
    return UUID(str(user.id))


def get_role(user = Depends(get_current_user)) -> Role:
    """
    Papel aplicacional do utilizador autenticado.

    Vem do app_metadata da conta no Supabase — que só é editável via
    dashboard/Admin API, nunca pelo próprio utilizador (signup/update não
    mexem nisto), por isso é seguro usar para controlo de acesso.

    Nota: não confundir com o campo user.role do Supabase (esse é interno ao
    GoTrue — normalmente "authenticated" — e não tem nada a ver com papéis
    da aplicação).

    Contas sem "role" definido em app_metadata são tratadas como Role.CLIENT
    (o caso normal, de longe a maioria das contas). Um valor inesperado (ex:
    erro de digitação ao editar à mão no dashboard) também cai em
    Role.CLIENT, em vez de rebentar o pedido com 500 — mais restrito por
    omissão em vez de falhar de forma pouco clara.
    """
    app_metadata = user.app_metadata or {}
    raw_role = app_metadata.get("role", Role.CLIENT.value)

    try:
        return Role(raw_role)
    except ValueError:
        return Role.CLIENT


def require_role(required_role : Role):
    """
    Fábrica de dependency para proteger rotas por papel aplicacional.

    Uso: _ : Role = Depends(require_role(Role.STAFF))

    Para uma conta ter o papel staff, é preciso ires ao dashboard do
    Supabase (Authentication > Users > [a tua conta] > Raw App Meta Data) e
    adicionares {"role": "staff"} manualmente — não há nenhum fluxo na API
    para uma conta se autopromover a staff, de propósito.
    """
    def dependency(role : Role = Depends(get_role)) -> Role:
        if role != required_role:
            raise AuthorizationError(
                f"Esta operação está reservada a utilizadores com o papel '{required_role.value}'"
            )
        return role

    return dependency


# Instância partilhada para o caso mais comum — importar isto em vez de
# chamar require_role(Role.STAFF) em cada rota (evita repetir o mesmo
# call site e permite ao FastAPI reconhecer/cachear a mesma dependency
# dentro de um pedido).
require_staff = require_role(Role.STAFF)
