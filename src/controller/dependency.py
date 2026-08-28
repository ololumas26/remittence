from src.service.client_service import ClientService
from src.service.document_service import DocumentService
from src.service.remittance_service import RemittanceService
from src.service.auth_service import AuthService
from src.database.db import session_DP
from src.repository.client_repository import SqlClientRepository
from src.repository.document_repository import SqlDocumentRepository
from src.repository.remittance_repository import SqlRemittanceRepository
from src.supabase.server import client
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Annotated
from src.external.service.file_storage_service import FileStorageService
from src.external.repo.file_storage_repo import SupabaseFileStorage
from src.exception.exceptions import AuthenticationError
from src.model.client import Client

def get_client_service(session : session_DP):
    return ClientService(SqlClientRepository(session))


def get_document_service(session : session_DP):
    file_storage = SupabaseFileStorage(client)
    file_storage_service = FileStorageService(file_storage)
    return DocumentService(SqlDocumentRepository(session), SqlClientRepository(session),file_storage_service)


def get_remittance_service(session : session_DP):
    return RemittanceService(SqlRemittanceRepository(session), SqlClientRepository(session), SqlDocumentRepository(session))


def get_auth_service(client_service : ClientService = Depends(get_client_service)):
    return AuthService(client, client_service)


# auto_error=False para nós controlarmos a resposta de erro (mantém o
# formato {data, error, message} da API em vez do 403 genérico do FastAPI
# quando o header Authorization vem em falta).
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials : Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    auth_service : AuthService = Depends(get_auth_service),
):
    if credentials is None:
        raise AuthenticationError("Token de autenticação em falta")

    return auth_service.get_current_user(credentials.credentials)


def get_current_client(
    user = Depends(get_current_user),
    client_service : ClientService = Depends(get_client_service),
) -> Client:
    return client_service.get_by_auth_user_id(user.id)
