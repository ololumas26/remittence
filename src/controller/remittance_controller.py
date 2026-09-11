from fastapi import APIRouter, Depends, Query, Request, status
from typing import Annotated
from src.constant.app_constant import APP_PREFIX
from src.dto.remittance_dto import RemittanceOut, RejectRemittance
from src.dto.admin_dto import RemittanceAdminOut
from src.dto.filter import RemittanceFilterParams
from src.controller.dependency import get_remittance_service, get_current_client
from src.service.remittance_service import RemittanceService
from src.dto.response import success_response, paginated_response
from src.exception.exceptions import ResourceNotFoundError
from src.model.client import Client
from src.security.client_ip import get_client_ip
from src.security.dependencies import require_staff, Role
from src.security.rate_limit import limiter

remittance_route = APIRouter(prefix=f'{APP_PREFIX}/remittance', tags=['remittances'])


def _ensure_owner(remittance, client : Client):
    # Mesma resposta de um id inexistente propositadamente — não confirmamos
    # a um cliente que uma remessa de outra pessoa existe.
    if remittance.client_id != client.id:
        raise ResourceNotFoundError(f"Remessa com id {remittance.id} não encontrada")

# Já não há POST "/" aqui: criar uma remessa sem pagamento associado ficou proibido quando a
# rota de pagamento (POST /payment/, ver payment_controller.py) passou a ser o único sítio onde
# um cliente consegue submeter uma remessa — chamar RemittanceService.submit() diretamente
# (como este endpoint fazia) deixava criar remessas com payment_id nulo, ou seja, "grátis". O
# método RemittanceService.submit() em si ainda existe mas já não tem nenhum utilizador.


@remittance_route.patch("/{id}/send")
@limiter.limit("30/minute")
def mark_as_sent(
    request : Request,
    id,
    remittance_service : RemittanceService = Depends(get_remittance_service),
    _ : Role = Depends(require_staff),
):
    remittance = remittance_service.mark_as_sent(id)
    return success_response(
        data=RemittanceOut.model_validate(remittance),
        message="Remessa marcada como enviada",
    )


@remittance_route.patch("/{id}/reject")
@limiter.limit("30/minute")
def mark_as_rejected(
    request : Request,
    id,
    reject_data : RejectRemittance,
    remittance_service : RemittanceService = Depends(get_remittance_service),
    _ : Role = Depends(require_staff),
):
    remittance = remittance_service.mark_as_rejected(id, note=reject_data.note)
    return success_response(
        data=RemittanceOut.model_validate(remittance),
        message="Remessa marcada como rejeitada",
    )


@remittance_route.get("/{id}", status_code=status.HTTP_200_OK)
@limiter.limit("30/minute")
def get_remittance(
    request : Request,
    id,
    client : Client = Depends(get_current_client),
    remittance_service : RemittanceService = Depends(get_remittance_service),
):
    remittance = remittance_service.get_remittance_by_id(id)
    _ensure_owner(remittance, client)
    remittance_out = RemittanceOut.model_validate(remittance)
    remittance_out.payment_status = remittance_service.get_payment_status(remittance)
    return success_response(
        data=remittance_out
    )


@remittance_route.get("/")
@limiter.limit("30/minute")
def get_all(
    request : Request,
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


@remittance_route.get("/admin/all")
@limiter.limit("30/minute")
def get_all_admin(
    request : Request,
    filter : Annotated[RemittanceFilterParams, Query()],
    remittance_service : RemittanceService = Depends(get_remittance_service),
    _ : Role = Depends(require_staff),
):
    # Ao contrário de get_all (acima), não sobrepõe filter.client_id — um membro do staff pode
    # ver/filtrar remessas de qualquer cliente, é esse o objetivo desta rota.
    remittances, total = remittance_service.get_all(filter)
    data = [RemittanceAdminOut.model_validate(remittance) for remittance in remittances]

    return paginated_response(data=data, total=total, limit=filter.limit, offset=filter.offset)
