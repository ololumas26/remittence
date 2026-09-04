from fastapi import APIRouter, Depends, Request, status
from src.constant.app_constant import APP_PREFIX
from src.dto.auth_dto import SignUp, Login, RefreshToken, TokenOut, ForgotPassword, ResetPassword, GoogleSignIn, SessionIdentityOut
from src.security.dependencies import get_auth_service, get_current_user
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


@auth_route.post("/google")
@limiter.limit("10/minute")
def google_sign_in(request: Request, google_sign_in: GoogleSignIn, auth_service: AuthService = Depends(get_auth_service)):
    token = auth_service.sign_in_with_google(google_sign_in.id_token)
    return success_response(data=TokenOut.model_validate(token))


@auth_route.get("/me")
@limiter.limit("30/minute")
def get_session_identity(request: Request, user = Depends(get_current_user)):
    # Não é o perfil de KYC (isso é GET /client/me, e pode ainda não existir — ver
    # AuthService.sign_in_with_google) — é só quem esta conta Auth diz que é, para pré-preencher
    # o ecrã de completar perfil sem pedir outra vez o que o provider (ex: Google) já deu.
    metadata = user.user_metadata or {}
    name = metadata.get("full_name") or metadata.get("name")
    identity = SessionIdentityOut(email=user.email, name=name)
    return success_response(data=identity)


@auth_route.post("/forgot-password")
@limiter.limit("5/minute")
def forgot_password(
    request: Request,
    forgot_password: ForgotPassword,
    auth_service: AuthService = Depends(get_auth_service),
):
    auth_service.forgot_password(forgot_password.email)
    # Mensagem sempre igual, exista ou não a conta — ver AuthService.forgot_password.
    return success_response(
        data=None,
        message="Se existir uma conta com este email, vais receber um código de recuperação.",
    )


@auth_route.post("/reset-password")
@limiter.limit("10/minute")
def reset_password(
    request: Request,
    reset_password: ResetPassword,
    auth_service: AuthService = Depends(get_auth_service),
):
    token = auth_service.reset_password(reset_password.email, reset_password.token, reset_password.new_password)
    return success_response(data=TokenOut.model_validate(token), message="Password alterada com sucesso")
