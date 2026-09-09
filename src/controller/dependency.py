from uuid import UUID
from src.service.document_service import DocumentService
from src.service.remittance_service import RemittanceService
from src.service.recipient_service import RecipientService
from src.service.client_service import ClientService
from src.database.db import session_DP
from src.repository.client_repository import SqlClientRepository
from src.repository.document_repository import SqlDocumentRepository
from src.repository.remittance_repository import SqlRemittanceRepository
from src.repository.recipient_repository import SqlRecipientRepository
from src.repository.payment_transaction_repository import SqlPaymentTransactionRepository
from src.supabase.server import client, admin_client
from fastapi import Depends
from src.external.service.file_storage_service import FileStorageService
from src.external.repo.file_storage_repo import SupabaseFileStorage
from src.external.service.geolocation_service import GeolocationService
from src.external.service.email_service import EmailService
from src.model.client import Client
from src.exception.exceptions import ResourceNotFoundError
from src.security.dependencies import get_client_service, get_current_user
from src.service.payment_service import PaymentService
from src.external.service.stripe_mbway_service import StripeMbwayGateway
from src.service.notification_service import NotificationService
from src.repository.notification_repository import SqlNotificationRepository
from src.repository.payment_repository import SqlPaymentRepository



# get_client_service fica re-exportado daqui (agora definido em
# src.security.dependencies, junto com o resto da identidade/autenticação)
# para não obrigar a mexer em todos os controllers que já o importam a
# partir deste módulo.


def get_document_service(session : session_DP):
    file_storage = SupabaseFileStorage(admin_client)
    file_storage_service = FileStorageService(file_storage)
    return DocumentService(SqlDocumentRepository(session), SqlClientRepository(session),file_storage_service)


# Uma única instância partilhada: o Reader do geoip2 abre o ficheiro .mmdb
# uma vez (lazy, na primeira consulta) e é seguro para reutilizar entre pedidos.
_geolocation_service = GeolocationService()


def get_geolocation_service() -> GeolocationService:
    return _geolocation_service


# Idem: EmailService não guarda estado nenhum entre pedidos (a api_key só é lida uma vez do
# ambiente, ver email_service.py), por isso uma instância partilhada chega.
_email_service = EmailService()


def get_email_service() -> EmailService:
    return _email_service


# Mesma razão da instância partilhada acima: o gateway não guarda estado entre pedidos (as
# chaves da Stripe só são lidas do ambiente uma vez, ver stripe_mbway_service.py).
_stripe_mbway_gateway = StripeMbwayGateway()


def get_stripe_mbway_gateway() -> StripeMbwayGateway:
    return _stripe_mbway_gateway


def get_recipient_service(session : session_DP):
    return RecipientService(SqlRecipientRepository(session), SqlClientRepository(session))


def get_remittance_service(
    session : session_DP,
    geolocation_service : GeolocationService = Depends(get_geolocation_service),
    email_service : EmailService = Depends(get_email_service),
):
    return RemittanceService(
        SqlRemittanceRepository(session),
        SqlClientRepository(session),
        SqlDocumentRepository(session),
        SqlRecipientRepository(session),
        geolocation_service,
        email_service,
        SqlPaymentRepository(session)
    )


def get_current_client(
    user = Depends(get_current_user),
    client_service : ClientService = Depends(get_client_service),
) -> Client:
    user_id = UUID(str(user.id))

    try:
        return client_service.get_by_auth_user_id(user_id)
    except ResourceNotFoundError:
        # Ainda sem perfil — tenta criar automaticamente a partir dos dados
        # guardados em user_metadata no signup (ver AuthService.sign_up).
        # Se não houver metadata suficiente, isto simplesmente relança o
        # mesmo ResourceNotFoundError de sempre.
        return client_service.create_from_signup_metadata(
            auth_user_id=user_id,
            email=user.email,
            metadata=user.user_metadata or {},
        )


def get_payment_service(
    session : session_DP,
    remittance_service : RemittanceService = Depends(get_remittance_service),
    mbway_gateway : StripeMbwayGateway = Depends(get_stripe_mbway_gateway),
):
    payment_transaction_repository = SqlPaymentTransactionRepository(session)
    payment_repository = SqlPaymentRepository(session)
    return PaymentService(remittance_service, payment_transaction_repository, payment_repository, mbway_gateway)


def get_notification_service(session: session_DP):
    return NotificationService(SqlNotificationRepository(session))
