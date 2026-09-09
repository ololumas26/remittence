from fastapi import APIRouter, Depends, Query, Request, status
from src.constant.app_constant import APP_PREFIX
from src.controller.dependency import get_payment_service, get_current_client
from src.security.rate_limit import limiter
from src.service.payment_service import PaymentService
from src.dto.payment_dto import CreatePayment
from src.model.client import Client

from src.database.db import session_DP
from sqlmodel import Session
from src.security.client_ip import get_client_ip
payment_route = APIRouter(prefix=f'{APP_PREFIX}/payment', tags=['payment'])


@payment_route.post('/')
@limiter.limit("5/minute")
def submit(
    request : Request,
    create_payment : CreatePayment,
    client : Client = Depends(get_current_client),
    payment_service : PaymentService = Depends(get_payment_service)
):
    # Mesma proteção que já existia em remittance_controller.submit: um cliente só pode
    # submeter remessas em seu próprio nome — ignora/sobrepõe qualquer client_id vindo do corpo
    # do pedido (agora aninhado em create_payment.remittance, não mais direto no corpo).
    create_payment.remittance.client_id = client.id
    payment_service.execute_payment(create_payment, ip_address=get_client_ip(request))
    return "Rota de pagamento"
