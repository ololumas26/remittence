import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from src.logging_config import configure_logging
from src.security.rate_limit import limiter
from src.controller.auth_controller import auth_route
from src.controller.client_controller import client_route
from src.controller.document_controller import document_route
from src.controller.recipient_controller import recipient_route
from src.controller.remittance_controller import remittance_route
from src.controller.payment_controller import payment_route
from src.exception.handlers import register_exception_handlers


configure_logging()


app = FastAPI(
    title="Remittance api",
    version='1.0'
)

# ALLOWED_ORIGINS: lista separada por vírgulas dos domínios do frontend que
# podem chamar esta API a partir do browser (ex: https://app.exemplo.com).
# Por omissão fica vazia — nenhum origin é permitido — em vez de "*", para
# não abrir a API a qualquer site por esquecimento em produção.
allowed_origins = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

routes = [
    auth_route,
    client_route,
    document_route,
    recipient_route,
    remittance_route,
    payment_route
]

for route in routes:
    app.include_router(route)

register_exception_handlers(app)
