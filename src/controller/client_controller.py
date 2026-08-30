from fastapi import APIRouter, Depends, Query, status
from src.constant.app_constant import APP_PREFIX
from src.dto.client_dto import CreateClient, UpdateClient, ClientOut
from src.security.dependencies import get_client_service, get_current_user, require_staff, Role
from src.controller.dependency import get_current_client
from src.service.client_service import ClientService
from src.dto.filter import FilterParams
from src.dto.response import success_response, paginated_response
from src.model.client import Client
from typing import Annotated


client_route = APIRouter(prefix=f'{APP_PREFIX}/client', tags=['clients'])


@client_route.post("/", status_code=status.HTTP_201_CREATED)
def create(
    create_client : CreateClient,
    user = Depends(get_current_user),
    client_service : ClientService = Depends(get_client_service),
):
    # A conta (email/password) já existe no Supabase Auth a esta altura —
    # aqui só criamos o perfil de KYC e ligamo-lo a essa conta (user.id).
    client = client_service.create(create_client, auth_user_id=user.id)
    return success_response(
        data=ClientOut.model_validate(client),
        message="Cliente criado com sucesso",
    )


@client_route.get("/")
def get_all(
    filter : Annotated[FilterParams, Query()],
    client_service : ClientService = Depends(get_client_service),
    _ : Role = Depends(require_staff),
):
    clients, total = client_service.get_all(filter)
    data = [ClientOut.model_validate(client) for client in clients]

    return paginated_response(data=data, total=total, limit=filter.limit, offset=filter.offset)


@client_route.delete("/me")
def delete_me(client : Client = Depends(get_current_client), client_service : ClientService = Depends(get_client_service)):
    client_service.delete(str(client.id))
    return success_response(data=None)


@client_route.put("/me")
def update_me(
    update_client : UpdateClient,
    client : Client = Depends(get_current_client),
    client_service : ClientService = Depends(get_client_service),
):
    updated_client = client_service.update(str(client.id), update_client)
    return success_response(data=ClientOut.model_validate(updated_client))


@client_route.get("/me")
def get_me(client : Client = Depends(get_current_client)):
    return success_response(data=ClientOut.model_validate(client))
