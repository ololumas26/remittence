from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.dto.response import error_response
from src.exception.exceptions import (
    AppException,
    UnderageClientError,
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
    InvalidIdentifierError,
    ExpiredDocumentError,
    FileUploadError,
    DocumentNotEditableError,
    DocumentNotDeletableError,
    ClientNotVerifiedError,
    InvalidAmountError,
    SameCurrencyError,
    SourceCurrencyError,
    InvalidRemittanceStatusError,
)


# Mapeamento exceção de domínio -> status HTTP autoexplicativo
STATUS_BY_EXCEPTION = {
    UnderageClientError: status.HTTP_400_BAD_REQUEST,
    InvalidIdentifierError: status.HTTP_400_BAD_REQUEST,
    ExpiredDocumentError: status.HTTP_400_BAD_REQUEST,
    DocumentNotEditableError: status.HTTP_400_BAD_REQUEST,
    DocumentNotDeletableError: status.HTTP_400_BAD_REQUEST,
    ClientNotVerifiedError: status.HTTP_400_BAD_REQUEST,
    InvalidAmountError: status.HTTP_400_BAD_REQUEST,
    SameCurrencyError: status.HTTP_400_BAD_REQUEST,
    SourceCurrencyError: status.HTTP_400_BAD_REQUEST,
    InvalidRemittanceStatusError: status.HTTP_400_BAD_REQUEST,
    ResourceAlreadyExistsError: status.HTTP_409_CONFLICT,
    ResourceNotFoundError: status.HTTP_404_NOT_FOUND,
    # 502: a falha é do storage externo (Supabase), não de algo que o cliente enviou errado.
    FileUploadError: status.HTTP_502_BAD_GATEWAY,
}

DEFAULT_APP_EXCEPTION_STATUS = status.HTTP_400_BAD_REQUEST


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    status_code = STATUS_BY_EXCEPTION.get(type(exc), DEFAULT_APP_EXCEPTION_STATUS)

    return JSONResponse(
        status_code=status_code,
        content=error_response(error=exc.code, message=str(exc)),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    first_error = exc.errors()[0]
    field = ".".join(str(part) for part in first_error["loc"] if part != "body")
    message = f"{field}: {first_error['msg']}" if field else first_error["msg"]

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response(error="VALIDATION_ERROR", message=message),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Rede de segurança: qualquer exceção não prevista cai aqui em vez de
    # vazar uma página de erro genérica do Starlette/stack trace.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(
            error="INTERNAL_ERROR",
            message="Ocorreu um erro interno. Tenta novamente mais tarde.",
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
