from fastapi import FastAPI
from src.controller.client_controller import client_route
from src.controller.document_controller import document_route
from src.exception.handlers import register_exception_handlers



app = FastAPI(
    title="Remittance api",
    version='1.0'
)

routes = [
    client_route,
    document_route,
]

for route in routes:
    app.include_router(route)

register_exception_handlers(app)
