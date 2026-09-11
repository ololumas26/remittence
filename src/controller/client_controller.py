from fastapi import APIRouter, Depends, Query, Request, UploadFile, status
from src.constant.app_constant import APP_PREFIX
from src.dto.client_dto import CreateClient, UpdateClient, ClientOut
from src.dto.document_dto import DocumentOut
from src.security.dependencies import get_client_service, get_current_user, require_staff, Role, get_auth_service
from src.controller.dependency import get_current_client, get_kyc_service, get_document_service
from src.service.kyc_service import KycService
from src.service.document_service import DocumentService
from src.security.rate_limit import limiter
from src.service.client_service import ClientService
from src.service.auth_service import AuthService
from src.dto.filter import FilterParams, DocumentFilterParams
from src.dto.response import success_response, paginated_response
from src.model.client import Client
from typing import Annotated


client_route = APIRouter(prefix=f'{APP_PREFIX}/client', tags=['clients'])


@client_route.post("/", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create(
    request : Request,
    create_client : CreateClient,
    user = Depends(get_current_user),
    client_service : ClientService = Depends(get_client_service),
):
    # A conta (email/password) já existe no Supabase Auth a esta altura —
    # aqui só criamos o perfil de KYC e ligamo-lo a essa conta (user.id).
    client = client_service.create(create_client, auth_user_id=user.id)
    return success_response(
        data=ClientOut.model_validate(client),
        message="Cliente criado com sucesso",
    )


@client_route.get("/")
@limiter.limit("30/minute")
def get_all(
    request : Request,
    filter : Annotated[FilterParams, Query()],
    client_service : ClientService = Depends(get_client_service),
    _ : Role = Depends(require_staff),
):
    clients, total = client_service.get_all(filter)
    data = [ClientOut.model_validate(client) for client in clients]

    return paginated_response(data=data, total=total, limit=filter.limit, offset=filter.offset)


@client_route.delete("/me")
@limiter.limit("5/minute")
def delete_me(
    request : Request,
    client : Client = Depends(get_current_client),
    client_service : ClientService = Depends(get_client_service),
    auth_service : AuthService = Depends(get_auth_service),
):
    # A conta no Auth é apagada primeiro: enquanto ela existir,
    # get_current_client recria automaticamente o perfil local a partir do
    # user_metadata no próximo pedido autenticado — apagar só o perfil
    # local "ressuscitaria" a conta.
    if client.auth_user_id is not None:
        auth_service.delete_account(client.auth_user_id)
    client_service.delete(str(client.id))
    return success_response(data=None)


@client_route.put("/me")
@limiter.limit("10/minute")
def update_me(
    request : Request,
    update_client : UpdateClient,
    client : Client = Depends(get_current_client),
    client_service : ClientService = Depends(get_client_service),
):
    updated_client = client_service.update(str(client.id), update_client)
    return success_response(data=ClientOut.model_validate(updated_client))


@client_route.get("/me")
@limiter.limit("30/minute")
def get_me(request : Request, client : Client = Depends(get_current_client)):
    return success_response(data=ClientOut.model_validate(client))


@client_route.get("/me/kyc-status")
@limiter.limit("30/minute")
def get_my_kyc_status(
    request : Request,
    client : Client = Depends(get_current_client),
    kyc_service : KycService = Depends(get_kyc_service),
):
    # get_status já devolve um KycStatusOut pronto, não um objeto ORM — não
    # precisa de passar por model_validate outra vez.
    status = kyc_service.get_status(client.id)
    return success_response(data=status)


@client_route.put("/me/photo")
@limiter.limit("5/minute")
async def update_my_photo(
    request : Request,
    file : UploadFile,
    client : Client = Depends(get_current_client),
    client_service : ClientService = Depends(get_client_service),
):

    updated_client = await client_service.update_photo(str(client.id), file)
    return success_response(
        data=ClientOut.model_validate(updated_client),
        message="Foto de perfil atualizada com sucesso",
    )


@client_route.delete("/me/photo")
@limiter.limit("5/minute")
def delete_my_photo(
    request : Request,
    client : Client = Depends(get_current_client),
    client_service : ClientService = Depends(get_client_service),
):
    updated_client = client_service.remove_photo(str(client.id))
    return success_response(data=ClientOut.model_validate(updated_client))


# Rotas abaixo são todas para staff (ver require_staff) veren perfil, KYC e documentos de
# QUALQUER cliente pelo id — nunca definidas antes de /me* acima, para o FastAPI não
# confundir o literal "me" com um valor de {id}.


@client_route.get("/{id}")
@limiter.limit("30/minute")
def get_by_id(
    request : Request,
    id,
    client_service : ClientService = Depends(get_client_service),
    _ : Role = Depends(require_staff),
):
    client = client_service.get_by_id(id)
    return success_response(data=ClientOut.model_validate(client))


@client_route.get("/{id}/kyc-status")
@limiter.limit("30/minute")
def get_kyc_status_by_id(
    request : Request,
    id,
    client_service : ClientService = Depends(get_client_service),
    kyc_service : KycService = Depends(get_kyc_service),
    _ : Role = Depends(require_staff),
):
    # get_by_id primeiro só para dar 404 consistente com o resto da API quando o
    # id não existe — KycService.get_status sozinho não sabe distinguir "cliente
    # inexistente" de "cliente sem documentos nenhuns" (as duas dão lista vazia).
    client = client_service.get_by_id(id)
    status = kyc_service.get_status(client.id)
    return success_response(data=status)


@client_route.get("/{id}/documents")
@limiter.limit("30/minute")
def get_documents_by_client_id(
    request : Request,
    id,
    filter : Annotated[FilterParams, Query()],
    client_service : ClientService = Depends(get_client_service),
    document_service : DocumentService = Depends(get_document_service),
    _ : Role = Depends(require_staff),
):
    client = client_service.get_by_id(id)

    document_filter = DocumentFilterParams(
        client_id=client.id,
        limit=filter.limit,
        offset=filter.offset,
        order_by=filter.order_by,
    )
    documents, total = document_service.get_all(document_filter)
    data = [DocumentOut.model_validate(document) for document in documents]

    return paginated_response(data=data, total=total, limit=filter.limit, offset=filter.offset)
