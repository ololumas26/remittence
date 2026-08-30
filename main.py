import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from src.logging_config import configure_logging
from src.security.rate_limit import limiter
from src.controller.auth_controller import auth_route
from src.controller.client_controller import client_route
from src.controller.document_controller import document_route
from src.controller.remittance_controller import remittance_route
from src.exception.handlers import register_exception_handlers


configure_logging()

# TODO: Base de dados em produção — DATABASE_URL ainda não está configurada
# para nenhum ambiente real (a app usa SQLite local por omissão fora de
# APP_ENV=production, onde isso agora falha ao arrancar — ver src/database/
# connection.py). Definir a connection string do Postgres (ex: Supabase) no
# .env de produção e correr `alembic upgrade head` contra essa base antes do
# primeiro deploy.

# TODO: Testes automatizados — a suite está praticamente vazia (só
# tests/validator/test_iban_validator.py ativo). Cobrir pelo menos os fluxos
# de submissão/transição de estado da remessa antes de lançar.

# TODO: Regras de compliance (AML) — limites por transação/cliente, listas
# de sanções, etc. Fora do âmbito do MVP mas a decidir antes de escalar.

# TODO: Implementar/configurar SMTP para envio de email de confirmação (hoje
# depende do provedor de email por omissão do Supabase, que tem limites
# baixos e não deve ser usado em produção).


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
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

routes = [
    auth_route,
    client_route,
    document_route,
    remittance_route,
]

for route in routes:
    app.include_router(route)

register_exception_handlers(app)
