from fastapi import APIRouter, Depends, Query, status, UploadFile, Form
from src.constant.app_constant import APP_PREFIX
from src.dto.document_dto import CreateDocument, UpdateDocument, DocumentOut
from src.controller.dependency import get_document_service, get_current_client
from src.service.document_service import DocumentService
from src.dto.response import success_response, paginated_response
from src.dto.filter import DocumentFilterParams
from src.exception.exceptions import ResourceNotFoundError
from src.model.client import Client
from typing import Annotated
from src.model.document import DocumentType

from datetime import date
from uuid import UUID

document_route = APIRouter(prefix=f'{APP_PREFIX}/document', tags=['documents'])


def _ensure_owner(document, client : Client):
    # Mesma resposta de um id inexistente propositadamente — não confirmamos
    # a um cliente que um documento de outra pessoa existe.
    if document.client_id != client.id:
        raise ResourceNotFoundError(f"Documento com id {document.id} não encontrado")


@document_route.post("/", status_code=status.HTTP_201_CREATED)
async def submit(
    document_type : Annotated[DocumentType, Form()],
    document_number : Annotated[str, Form()],
    expiration_date : Annotated[date, Form()],
    file : UploadFile,
    client : Client = Depends(get_current_client),
    document_service : DocumentService = Depends(get_document_service),
):
    create_document = CreateDocument(
        client_id=client.id,
        document_type=document_type,
        document_number=document_number,
        expiration_date=expiration_date,
    )
    document = await document_service.submit(create_document, file)
    return success_response(
        data=DocumentOut.model_validate(document),
        message="Documento submetido com sucesso",
    )


@document_route.get("/")
def get_all(
    filter : Annotated[DocumentFilterParams, Query()],
    client : Client = Depends(get_current_client),
    document_service : DocumentService = Depends(get_document_service),
):
    # Um cliente só pode listar os próprios documentos — ignora/sobrepõe
    # qualquer client_id vindo da query string.
    filter.client_id = client.id
    documents, total = document_service.get_all(filter)
    data = [DocumentOut.model_validate(document) for document in documents]

    return paginated_response(data=data, total=total, limit=filter.limit, offset=filter.offset)


@document_route.get("/{id}")
def get(id, client : Client = Depends(get_current_client), document_service : DocumentService = Depends(get_document_service)):
    document = document_service.get_by_id(id)
    _ensure_owner(document, client)
    return success_response(data=DocumentOut.model_validate(document))


@document_route.put("/{id}")
async def update(
    id,
    file : UploadFile,
    document_type : Annotated[DocumentType | None, Form()] = None,
    document_number : Annotated[str | None, Form()] = None,
    expiration_date : Annotated[date | None, Form()] = None,
    client : Client = Depends(get_current_client),
    document_service : DocumentService = Depends(get_document_service),
):
    _ensure_owner(document_service.get_by_id(id), client)

    update_document = UpdateDocument(
        document_type=document_type,
        document_number=document_number,
        expiration_date=expiration_date,
    )
    document = await document_service.update(id, update_document, file)
    return success_response(
        data=DocumentOut.model_validate(document),
        message="Documento atualizado com sucesso",
    )


@document_route.delete("/{id}")
def delete(id, client : Client = Depends(get_current_client), document_service : DocumentService = Depends(get_document_service)):
    _ensure_owner(document_service.get_by_id(id), client)
    document_service.delete(id)
    return success_response(data=None)
