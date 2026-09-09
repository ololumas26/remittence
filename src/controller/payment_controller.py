from fastapi import APIRouter, Depends, Request, status
from src.constant.app_constant import APP_PREFIX
from src.controller.dependency import get_payment_service, get_current_client
from src.security.rate_limit import limiter
from src.service.payment_service import PaymentService
from src.dto.payment_dto import CreatePayment
from src.dto.remittance_dto import RemittanceOut
from src.dto.response import success_response
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
    remittance, payment, redirect_url = payment_service.execute_payment(
        create_payment, ip_address=get_client_ip(request)
    )
    remittance_out = RemittanceOut.model_validate(remittance)
    remittance_out.payment_status = payment.status
    remittance_out.payment_redirect_url = redirect_url
    return success_response(
        data=remittance_out,
        message="Pagamento iniciado",
    )


@payment_route.post('/stripe/webhook')
@limiter.limit("60/minute")
async def stripe_webhook(
    request : Request,
    payment_service : PaymentService = Depends(get_payment_service)
):
    # Chamado pela própria Stripe (nunca pelo cliente da app) para confirmar de forma assíncrona
    # o resultado de um pagamento MB WAY — ver PaymentService.handle_stripe_webhook e o
    # comentário em Payment.status sobre a confirmação chegar sempre via webhook do processador.
    # O corpo tem de ser lido em bruto (não como JSON já interpretado) porque a verificação da
    # assinatura da Stripe é feita sobre os bytes exatos recebidos.
    payload = await request.body()
    signature = request.headers.get('stripe-signature')
    payment_service.handle_stripe_webhook(payload, signature)
    return "OK"
