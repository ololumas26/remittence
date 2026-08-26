from fastapi import APIRouter, Depends, Query, status
from typing import Annotated
from src.constant.app_constant import APP_PREFIX
from src.dto.remittance_dto import CreateRemittance, RemittanceOut
from src.dto.filter import RemittanceFilterParams
from src.controller.dependency import get_remittance_service
from src.service.remittance_service import RemittanceService
from src.dto.response import success_response, paginated_response


remittance_route = APIRouter(prefix=f'{APP_PREFIX}/remittance', tags=['remittances'])


@remittance_route.post("/", status_code=status.HTTP_201_CREATED)
def submit(create_remittance : CreateRemittance, remittance_service : RemittanceService = Depends(get_remittance_service)):
    remittance = remittance_service.submit(create_remittance)
    return success_response(
        data=RemittanceOut.model_validate(remittance),
        message="Remessa submetida com sucesso",
    )


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
def get_remittance(id,  remittance_service : RemittanceService = Depends(get_remittance_service)):
    response = remittance_service.get_remittance_by_id(id)
    return success_response(
        data=RemittanceOut.model_validate(response)
    )


@remittance_route.get("/")
def get_all(filter : Annotated[RemittanceFilterParams, Query()], remittance_service : RemittanceService = Depends(get_remittance_service)):
    remittances, total = remittance_service.get_all(filter)
    data = [RemittanceOut.model_validate(remittance) for remittance in remittances]

    return paginated_response(data=data, total=total, limit=filter.limit, offset=filter.offset)