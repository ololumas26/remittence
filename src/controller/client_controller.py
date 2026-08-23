from fastapi import APIRouter, Depends, Query, status
from src.constant.app_constant import APP_PREFIX
from src.dto.client_dto import CreateClient, UpdateClient, ClientOut
from src.controller.dependency import get_client_service
from src.service.client_service import ClientService
from src.dto.filter import FilterParams
from src.dto.response import success_response, paginated_response
from typing import Annotated


client_route = APIRouter(prefix=f'{APP_PREFIX}/client', tags=['clients'])


@client_route.post("/", status_code=status.HTTP_201_CREATED)
def create(create_client : CreateClient, client_service : ClientService = Depends(get_client_service)):
    client = client_service.create(create_client)
    return success_response(
        data=ClientOut.model_validate(client),
        message="Cliente criado com sucesso",
    )


@client_route.get("/")
def get_all(filter : Annotated[FilterParams, Query()], client_service : ClientService = Depends(get_client_service)):
    clients, total = client_service.get_all(filter)
    data = [ClientOut.model_validate(client) for client in clients]

    return paginated_response(data=data, total=total, limit=filter.limit, offset=filter.offset)


@client_route.delete("/{id}")
def delete(id, client_service : ClientService = Depends(get_client_service)):
    client_service.delete(id)
    return success_response(data=None)


@client_route.put("/{id}")
def update(id, update_client : UpdateClient, client_service : ClientService = Depends(get_client_service)):
    client = client_service.update(id, update_client)
    return success_response(data=ClientOut.model_validate(client))


@client_route.get("/{id}")
def get(id, client_service : ClientService = Depends(get_client_service)):
    client = client_service.get_by_id(id)
    return success_response(data=ClientOut.model_validate(client))
