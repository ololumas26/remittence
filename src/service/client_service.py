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
from src.external.service.file_storage_service import FileStorageService
from fastapi import UploadFile
from uuid import UUID
from datetime import datetime, timezone
from src.dto.filter import FilterParams


class ClientService:

    def __init__(self, client_repository : ClientRepository, file_storage_service : FileStorageService):
        self.client_repo = client_repository
        self.file_storage_service = file_storage_service

    def create(self, create_client : CreateClient, auth_user_id : UUID):

        parsed_auth_user_id = self._parse_id(auth_user_id)
        self._ensure_eligible(create_client, auth_user_id=parsed_auth_user_id)

        client = Client(**create_client.model_dump(), auth_user_id=parsed_auth_user_id)
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
                "Ainda não completaste o teu perfil de cliente com esta conta"
            )

        return client


    def create_from_signup_metadata(self, auth_user_id : UUID, email : str, metadata : dict) -> Client:
        """
        Cria o perfil de KYC automaticamente a partir dos dados guardados em
        user_metadata no momento do signup (ver AuthService.sign_up) — usado
        por get_current_client na primeira ação autenticada de uma conta que
        ainda não tem perfil, para não obrigar o cliente a preencher outra
        vez nome/telefone/data de nascimento depois de confirmar o email.

        Se a metadata estiver incompleta ou em falta (ex: conta staff criada
        diretamente no dashboard do Supabase, ou conta anterior a esta
        funcionalidade existir), não inventamos nada: cai no mesmo erro de
        sempre, a indicar que o perfil ainda não está completo. A validação
        "a sério" (email livre, idade mínima) continua a acontecer em
        create() — isto é só uma forma alternativa de montar o CreateClient,
        não um atalho que a evita.
        """
        try:
            create_client = CreateClient(
                name=metadata["name"],
                email=email,
                phone_number=metadata["phone_number"],
                birth_date=metadata["birth_date"],
            )
        except (KeyError, TypeError, ValueError):
            raise ResourceNotFoundError(
                "Ainda não completaste o teu perfil de cliente com esta conta"
            )

        return self.create(create_client, auth_user_id=auth_user_id)


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

        # Email é unique na BD (ver model/client.py) mas update_client não
        # passa pela mesma validação de elegibilidade que o signup — sem
        # este check, mudar para um email já usado por outra conta rebentava
        # num IntegrityError cru (500) em vez de um erro de domínio claro.
        new_email = update_client.email
        if new_email is not None and new_email != client.email:
            existing = self.client_repo.get_by_email(new_email)
            if existing and existing.id != client.id:
                raise ResourceAlreadyExistsError("Já existe uma conta com esse email")

        # A idade mínima só era verificada na criação (ver _ensure_eligible) — editar o perfil
        # (ex: "editar perfil" no frontend) deixava alterar a data de nascimento para uma que
        # tornasse o cliente menor sem qualquer validação server-side. RemittanceService também
        # reverifica isto no momento de submeter uma remessa, mas bloquear já aqui, na escrita,
        # é mais direto do que só na leitura seguinte.
        if update_client.birth_date is not None and get_18_year_date(update_client.birth_date) > get_current_date():
            raise UnderageClientError("Apenas clientes com 18+ anos podem manter a conta ativa")

        for key, value in update_client.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(client, key, value)

        client.updated_at = datetime.now(timezone.utc)

        return self.client_repo.save(client)


    async def update_photo(self, client_id : str, file : UploadFile) -> Client:
        """
        Substitui a foto de perfil do cliente. O ficheiro antigo (se existir) só é apagado do
        Supabase Storage depois de a nova foto ficar gravada com sucesso no cliente — mesma
        ordem de DocumentService.update, para nunca ficar sem nenhuma das duas em caso de falha
        a meio.
        """
        client = self._get_or_raise(client_id)

        old_image_url = client.image_url
        new_image_url = await self.file_storage_service.execute(file, client.id)

        client.image_url = new_image_url
        client.updated_at = datetime.now(timezone.utc)

        updated_client = self.client_repo.save(client)

        if old_image_url:
            self.file_storage_service.delete_previous(old_image_url)

        return updated_client

    def remove_photo(self, client_id : str) -> Client:
        """Remove a foto de perfil — o frontend volta a mostrar as iniciais do nome."""
        client = self._get_or_raise(client_id)

        old_image_url = client.image_url
        if old_image_url is None:
            return client

        client.image_url = None
        client.updated_at = datetime.now(timezone.utc)

        updated_client = self.client_repo.save(client)
        self.file_storage_service.delete_previous(old_image_url)

        return updated_client

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
