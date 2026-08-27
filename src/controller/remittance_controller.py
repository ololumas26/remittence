from fastapi import APIRouter, Depends, Query, status
from typing import Annotated
from src.constant.app_constant import APP_PREFIX
from src.dto.remittance_dto import CreateRemittance, RemittanceOut
from src.dto.filter import RemittanceFilterParams
from src.controller.dependency import get_remittance_service, get_current_client
from src.service.remittance_service import RemittanceService
from src.dto.response import success_response, paginated_response
from src.exception.exceptions import ResourceNotFoundError
from src.model.client import Client


remittance_route = APIRouter(prefix=f'{APP_PREFIX}/remittance', tags=['remittances'])


def _ensure_owner(remittance, client : Client):
    # Mesma resposta de um id inexistente propositadamente — não confirmamos
    # a um cliente que uma remessa de outra pessoa existe.
    if remittance.client_id != client.id:
        raise ResourceNotFoundError(f"Remessa com id {remittance.id} não encontrada")


@remittance_route.post("/", status_code=status.HTTP_201_CREATED)
def submit(
    create_remittance : CreateRemittance,
    client : Client = Depends(get_current_client),
    remittance_service : RemittanceService = Depends(get_remittance_service),
):
    # Um cliente só pode submeter remessas em seu próprio nome — ignora/sobrepõe
    # qualquer client_id vindo no corpo do pedido.
    create_remittance.client_id = client.id
    remittance = remittance_service.submit(create_remittance)
    return success_response(
        data=RemittanceOut.model_validate(remittance),
        message="Remessa submetida com sucesso",
    )


# TODO: mark_as_sent/mark_as_rejected deviam exigir um papel de staff, não
# estarem abertas como estão agora — fica assim por decisão consciente enquanto
# não existe autenticação de equipa interna (ver TODO em main.py).
@remittance_route.patch("/{id}/send")
def mark_as_sent(id, remittance_service : RemittanceService = Depends(get_remittance_service)):
    remittance = remittance_service.mark_as_sent(id)
    return success_response(
        data=RemittanceOut.model_validate(remittance),
        message="Remessa marcada como enviada",
    )


@remittance_route.patch("/{id}/reject")
def mark_as_rejected(id,  remittance_service : RemittanceService = Depends(get_remittance_service)):
    remittance = remittance_service.mark_as_rejected(id)
    return success_response(
        data=RemittanceOut.model_validate(remittance),
        message="Remessa marcada como rejeitada",
    )


@remittance_route.get("/{id}", status_code=status.HTTP_200_OK)
def get_remittance(
    id,
    client : Client = Depends(get_current_client),
    remittance_service : RemittanceService = Depends(get_remittance_service),
):
    remittance = remittance_service.get_remittance_by_id(id)
    _ensure_owner(remittance, client)
    return success_response(
        data=RemittanceOut.model_validate(remittance)
    )


@remittance_route.get("/")
def get_all(
    filter : Annotated[RemittanceFilterParams, Query()],
    client : Client = Depends(get_current_client),
    remittance_service : RemittanceService = Depends(get_remittance_service),
):
    # Um cliente só pode listar as próprias remessas — ignora/sobrepõe
    # qualquer client_id vindo da query string.
    filter.client_id = client.id
    remittances, total = remittance_service.get_all(filter)
    data = [RemittanceOut.model_validate(remittance) for remittance in remittances]

    return paginated_response(data=data, total=total, limit=filter.limit, offset=filter.offset)
