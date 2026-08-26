from fastapi import FastAPI
from src.controller.client_controller import client_route
from src.controller.document_controller import document_route
from src.controller.remittance_controller import remittance_route
from src.exception.handlers import register_exception_handlers


# TODO: Autenticação e autorização — hoje qualquer chamada acede a qualquer
# endpoint sem qualquer verificação de quem está a pedir. Decidir quem se
# autentica (cliente final? equipa interna de operações? os dois, com papéis
# diferentes?) e restringir endpoints sensíveis por papel — em particular
# mark_as_sent/mark_as_rejected e o acesso a dados de outros clientes.
# Como já se usa Supabase para storage, o Supabase Auth pode poupar trabalho
# em vez de JWT/OAuth escrito de raiz.

# TODO: Base de dados em produção — DATABASE_URL ainda não está configurada
# para nenhum ambiente real (a app usa SQLite local por omissão). Definir a
# connection string do Postgres (ex: Supabase) no .env de produção e correr
# `alembic upgrade head` contra essa base antes do primeiro deploy.

# TODO: Testes automatizados — a suite está praticamente vazia (só
# tests/validator/test_iban_validator.py ativo). Cobrir pelo menos os fluxos
# de submissão/transição de estado da remessa antes de lançar.

# TODO: CORS — sem configuração de CORS no FastAPI; necessário assim que
# houver um frontend a chamar esta API a partir de outro domínio.

# TODO: Logging/observabilidade — sem logs estruturados nem forma de
# investigar falhas em produção além do handler genérico de erro 500.

# TODO: Regras de compliance (AML) — limites por transação/cliente, listas
# de sanções, etc. Fora do âmbito do MVP mas a decidir antes de escalar.


app = FastAPI(
    title="Remittance api",
    version='1.0'
)

routes = [
    client_route,
    document_route,
    remittance_route,
]

for route in routes:
    app.include_router(route)

register_exception_handlers(app)
