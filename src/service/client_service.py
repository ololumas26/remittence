from src.model.repo.client_repo import ClientRepository
from src.dto.client_dto import CreateClient, UpdateClient
from src.service.age_calculator import get_18_year_date, get_current_date
from src.exception.exceptions import (
    UnderageClientError,
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
    InvalidIdentifierError,
)
from src.model.client import Client
from uuid import UUID
from datetime import datetime, timezone
from src.dto.filter import FilterParams


class ClientService:

    def __init__(self, client_repository : ClientRepository):
        self.client_repo = client_repository

    def create(self, create_client : CreateClient, auth_user_id : UUID):

        self._ensure_eligible(create_client, auth_user_id=auth_user_id)

        client = Client(**create_client.model_dump(), auth_user_id=auth_user_id)
        return self.client_repo.save(client)


    def ensure_eligible(self, create_client : CreateClient) -> None:
        """
        Verifica se create_client pode ser registado (email ainda não usado,
        idade mínima), sem persistir nada. Usado pelo AuthService antes de
        criar a conta no Supabase — se a elegibilidade falhar aqui, nunca
        chegamos a criar a conta lá, evitando ficar com uma conta órfã sem
        perfil correspondente.
        """
        self._ensure_eligible(create_client, auth_user_id=None)


    def _ensure_eligible(self, create_client : CreateClient, auth_user_id : UUID | None) -> None:

        has_client = self.client_repo.get_by_email(create_client.email)

        if has_client:
            raise ResourceAlreadyExistsError("Já existe uma conta com esse email")

        if auth_user_id is not None and self.client_repo.get_by_auth_user_id(auth_user_id):
            raise ResourceAlreadyExistsError("Já tens um perfil de cliente associado a esta conta")

        if get_18_year_date(create_client.birth_date) > get_current_date():
            raise UnderageClientError("Apenas clientes com 18+ anos podem se registar")


    def get_by_id(self, client_id):
        return self._get_or_raise(client_id)


    def get_by_auth_user_id(self, auth_user_id : UUID) -> Client:
        client = self.client_repo.get_by_auth_user_id(auth_user_id)

        if not client:
            raise ResourceNotFoundError(
                "Ainda não completaste o teu perfil de cliente (POST /client/) com esta conta"
            )

        return client


    def get_all(self, filter : FilterParams):
        clients = self.client_repo.get_all(
            limit=filter.limit,
            offset=filter.offset,
            order_by=filter.order_by,
        )
        total = self.client_repo.count()

        return clients, total


    def delete(self, client_id : str):
        client = self._get_or_raise(client_id)
        self.client_repo.delete(client)


    def update(self, client_id : str, update_client : UpdateClient):

        client = self._get_or_raise(client_id)

        for key, value in update_client.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(client, key, value)

        client.updated_at = datetime.now(timezone.utc)

        return self.client_repo.save(client)


    def _get_or_raise(self, client_id : str) -> Client:
        client = self.client_repo.get_by_id(self._parse_id(client_id))

        if not client:
            raise ResourceNotFoundError(f"Cliente com id {client_id} não encontrado")

        return client


    @staticmethod
    def _parse_id(client_id : str) -> UUID:
        try:
            return UUID(str(client_id))
        except (ValueError, AttributeError, TypeError):
            raise InvalidIdentifierError(f"'{client_id}' não é um identificador válido")
