from fastapi import APIRouter, Depends, Request, status
from src.constant.app_constant import APP_PREFIX
from src.dto.auth_dto import SignUp, Login, RefreshToken, TokenOut
from src.security.dependencies import get_auth_service
from src.security.rate_limit import limiter
from src.service.auth_service import AuthService
from src.dto.response import success_response


auth_route = APIRouter(prefix=f'{APP_PREFIX}/auth', tags=['auth'])


# Limites por IP: signup/login são os alvos clássicos de abuso (criação em
# massa de contas, força bruta de password) — refresh é mais permissivo
# porque um cliente legítimo pode chamá-lo com alguma frequência.
@auth_route.post("/signup", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def sign_up(request: Request, sign_up: SignUp, auth_service: AuthService = Depends(get_auth_service)):
    token = auth_service.sign_up(sign_up)
    return success_response(
        data=TokenOut.model_validate(token),
        message="Conta criada com sucesso",
    )


@auth_route.post("/login")
@limiter.limit("10/minute")
def login(request: Request, login: Login, auth_service: AuthService = Depends(get_auth_service)):
    token = auth_service.login(login)
    return success_response(data=TokenOut.model_validate(token))


@auth_route.post("/refresh")
@limiter.limit("30/minute")
def refresh(request: Request, refresh_token: RefreshToken, auth_service: AuthService = Depends(get_auth_service)):
    token = auth_service.refresh(refresh_token.refresh_token)
    return success_response(data=TokenOut.model_validate(token))
