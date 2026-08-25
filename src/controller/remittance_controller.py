from fastapi import APIRouter, Depends, status
from src.constant.app_constant import APP_PREFIX
from src.dto.remittance_dto import CreateRemittance, RemittanceOut
from src.controller.dependency import get_remittance_service
from src.service.remittance_service import RemittanceService
from src.dto.response import success_response


remittance_route = APIRouter(prefix=f'{APP_PREFIX}/remittance', tags=['remittances'])


@remittance_route.post("/", status_code=status.HTTP_201_CREATED)
def submit(create_remittance : CreateRemittance, remittance_service : RemittanceService = Depends(get_remittance_service)):
    remittance = remittance_service.submit(create_remittance)
    return success_response(
        data=RemittanceOut.model_validate(remittance),
        message="Remessa submetida com sucesso",
    )
