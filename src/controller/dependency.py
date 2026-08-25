from src.service.client_service import ClientService
from src.service.document_service import DocumentService
from src.database.db import session_DP
from src.repository.client_repository import SqlClientRepository
from src.repository.document_repository import SqlDocumentRepository
from src.supabase.server import client
from fastapi import Depends
from src.external.service.file_storage_service import FileStorageService
from src.external.repo.file_storage_repo import SupabaseFileStorage

def get_client_service(session : session_DP):
    return ClientService(SqlClientRepository(session))


def get_document_service(session : session_DP):
    file_storage = SupabaseFileStorage(client)
    file_storage_service = FileStorageService(file_storage)
    return DocumentService(SqlDocumentRepository(session), SqlClientRepository(session),file_storage_service)



