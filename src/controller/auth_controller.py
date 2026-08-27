from fastapi import APIRouter, Depends, status
from src.constant.app_constant import APP_PREFIX
from src.dto.auth_dto import SignUp, Login, RefreshToken, TokenOut
from src.controller.dependency import get_auth_service
from src.service.auth_service import AuthService
from src.dto.response import success_response


auth_route = APIRouter(prefix=f'{APP_PREFIX}/auth', tags=['auth'])


@auth_route.post("/signup", status_code=status.HTTP_201_CREATED)
def sign_up(sign_up: SignUp, auth_service: AuthService = Depends(get_auth_service)):
    token = auth_service.sign_up(sign_up)
    return success_response(
        data=TokenOut.model_validate(token),
        message="Conta criada com sucesso",
    )


@auth_route.post("/login")
def login(login: Login, auth_service: AuthService = Depends(get_auth_service)):
    token = auth_service.login(login)
    return success_response(data=TokenOut.model_validate(token))


@auth_route.post("/refresh")
def refresh(refresh_token: RefreshToken, auth_service: AuthService = Depends(get_auth_service)):
    token = auth_service.refresh(refresh_token.refresh_token)
    return success_response(data=TokenOut.model_validate(token))
