from src.service.document_service import DocumentService
from src.service.remittance_service import RemittanceService
from src.service.client_service import ClientService
from src.database.db import session_DP
from src.repository.client_repository import SqlClientRepository
from src.repository.document_repository import SqlDocumentRepository
from src.repository.remittance_repository import SqlRemittanceRepository
from src.supabase.server import client
from fastapi import Depends
from src.external.service.file_storage_service import FileStorageService
from src.external.repo.file_storage_repo import SupabaseFileStorage
from src.external.service.geolocation_service import GeolocationService
from src.model.client import Client
from src.security.dependencies import get_client_service, get_user_id

# get_client_service fica re-exportado daqui (agora definido em
# src.security.dependencies, junto com o resto da identidade/autenticação)
# para não obrigar a mexer em todos os controllers que já o importam a
# partir deste módulo.


def get_document_service(session : session_DP):
    file_storage = SupabaseFileStorage(client)
    file_storage_service = FileStorageService(file_storage)
    return DocumentService(SqlDocumentRepository(session), SqlClientRepository(session),file_storage_service)


# Uma única instância partilhada: o Reader do geoip2 abre o ficheiro .mmdb
# uma vez (lazy, na primeira consulta) e é seguro para reutilizar entre pedidos.
_geolocation_service = GeolocationService()


def get_geolocation_service() -> GeolocationService:
    return _geolocation_service


def get_remittance_service(session : session_DP, geolocation_service : GeolocationService = Depends(get_geolocation_service)):
    return RemittanceService(SqlRemittanceRepository(session), SqlClientRepository(session), SqlDocumentRepository(session), geolocation_service)


def get_current_client(
    user_id = Depends(get_user_id),
    client_service : ClientService = Depends(get_client_service),
) -> Client:
    return client_service.get_by_auth_user_id(user_id)
