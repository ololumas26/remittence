from fastapi import APIRouter, Depends, Query, status
from typing import Annotated
from src.constant.app_constant import APP_PREFIX
from src.dto.recipient_dto import CreateRecipient, UpdateRecipient, RecipientOut
from src.dto.filter import RecipientFilterParams
from src.controller.dependency import get_recipient_service, get_current_client
from src.service.recipient_service import RecipientService
from src.dto.response import success_response, paginated_response
from src.exception.exceptions import ResourceNotFoundError
from src.model.client import Client

recipient_route = APIRouter(prefix=f'{APP_PREFIX}/recipient', tags=['recipients'])


def _ensure_owner(recipient, client : Client):
    # Mesma resposta de um id inexistente propositadamente — não confirmamos
    # a um cliente que um destinatário de outra pessoa existe.
    if recipient.client_id != client.id:
        raise ResourceNotFoundError(f"Destinatário com id {recipient.id} não encontrado")


@recipient_route.post("/", status_code=status.HTTP_201_CREATED)
def create(
    create_recipient : CreateRecipient,
    client : Client = Depends(get_current_client),
    recipient_service : RecipientService = Depends(get_recipient_service),
):
    # Um cliente só pode criar destinatários em seu próprio nome — ignora/sobrepõe
    # qualquer client_id vindo do corpo do pedido.
    create_recipient.client_id = client.id
    recipient = recipient_service.create(create_recipient)
    return success_response(
        data=RecipientOut.model_validate(recipient),
        message="Destinatário criado com sucesso",
    )


@recipient_route.get("/")
def get_all(
    filter : Annotated[RecipientFilterParams, Query()],
    client : Client = Depends(get_current_client),
    recipient_service : RecipientService = Depends(get_recipient_service),
):
    # Um cliente só pode listar os próprios destinatários — ignora/sobrepõe
    # qualquer client_id vindo da query string.
    filter.client_id = client.id
    recipients, total = recipient_service.get_all(filter)
    data = [RecipientOut.model_validate(recipient) for recipient in recipients]

    return paginated_response(data=data, total=total, limit=filter.limit, offset=filter.offset)


@recipient_route.get("/{id}")
def get(
    id,
    client : Client = Depends(get_current_client),
    recipient_service : RecipientService = Depends(get_recipient_service),
):
    recipient = recipient_service.get_by_id(id)
    _ensure_owner(recipient, client)
    return success_response(data=RecipientOut.model_validate(recipient))


@recipient_route.put("/{id}")
def update(
    id,
    update_recipient : UpdateRecipient,
    client : Client = Depends(get_current_client),
    recipient_service : RecipientService = Depends(get_recipient_service),
):
    _ensure_owner(recipient_service.get_by_id(id), client)
    recipient = recipient_service.update(id, update_recipient)
    return success_response(
        data=RecipientOut.model_validate(recipient),
        message="Destinatário atualizado com sucesso",
    )


@recipient_route.delete("/{id}")
def delete(
    id,
    client : Client = Depends(get_current_client),
    recipient_service : RecipientService = Depends(get_recipient_service),
):
    _ensure_owner(recipient_service.get_by_id(id), client)
    recipient_service.delete(id)
    return success_response(data=None)
