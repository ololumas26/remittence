from fastapi import APIRouter, Depends, status, UploadFile, Form
from src.constant.app_constant import APP_PREFIX
from src.dto.document_dto import CreateDocument, DocumentOut
from src.controller.dependency import get_document_service
from src.service.document_service import DocumentService
from src.dto.response import success_response
import io
from typing import Annotated
from src.model.document import DocumentType

from datetime import date
from uuid import UUID

document_route = APIRouter(prefix=f'{APP_PREFIX}/document', tags=['documents'])


@document_route.post("/", status_code=status.HTTP_201_CREATED)
async def submit(
    client_id : Annotated[UUID, Form()],
    document_type : Annotated[DocumentType, Form()],
    document_number : Annotated[str, Form()],
    expiration_date : Annotated[date, Form()],
    file : UploadFile,
    document_service : DocumentService = Depends(get_document_service),
):
    create_document = CreateDocument(
        client_id=client_id,
        document_type=document_type,
        document_number=document_number,
        expiration_date=expiration_date,
    )
    document = await document_service.submit(create_document, file)
    return success_response(
        data=DocumentOut.model_validate(document),
        message="Documento submetido com sucesso",
    )
