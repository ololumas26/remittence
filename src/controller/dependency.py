from src.service.client_service import ClientService
from src.database.db import session_DP
from src.repository.client_repository import SqlClientRepository


def get_client_service(session : session_DP):  
    return ClientService(SqlClientRepository(session))