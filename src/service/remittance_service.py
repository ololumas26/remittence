from src.model.repo.remittance_repo import RemittanceRepository
from src.model.repo.client_repo import ClientRepository
from src.model.repo.document_repo import DocumentRepository
from src.dto.remittance_dto import CreateRemittance
from src.dto.filter import RemittanceFilterParams
from src.model.remittance import Remittance, AllowedCoins, RemittanceStatus
from src.model.document import DocumentType, DocumentStatus
from src.service.age_calculator import get_current_date
from src.service.exchange_calculator import calculate_service_fee_amount, calculate_amount_converted
from src.constant.app_constant import MIN_AMOUNT, EXCHANGE_RATE, SERVICE_FEE_RATE
from src.exception.exceptions import (
    ResourceNotFoundError,
    ClientNotVerifiedError,
    InvalidAmountError,
    SameCurrencyError,
    SourceCurrencyError,
    InvalidRemittanceStatusError,
    InvalidIdentifierError,
)
from uuid import UUID
from datetime import datetime, timezone


# Documentos que servem como identificação pessoal — qualquer um destes, aprovado
# e ainda válido, conta pra verificação de KYC. O comprovativo de morada é à parte.
PERSONAL_DOCUMENT_TYPES = (DocumentType.BI, DocumentType.PASSAPORTE, DocumentType.TITULO_RESIDENCIA)


class RemittanceService:

    def __init__(self, remittance_repository : RemittanceRepository, client_repository : ClientRepository,
                 document_repository : DocumentRepository):
        self.remittance_repo = remittance_repository
        self.client_repo = client_repository
        self.document_repo = document_repository

    def _ensure_client_is_verified(self, client_id : UUID) -> None:
    
            documents = self.document_repo.get_by_client_id(client_id)
            today = get_current_date()
    
            has_valid_personal_document = any(
                document.document_type in PERSONAL_DOCUMENT_TYPES
                and document.status == DocumentStatus.APPROVED
                and document.expiration_date >= today
                for document in documents
            )

            #TODO: Reativar apenas quando melhorar a questão da s submissão do comprovativo de morada
            # has_valid_address_document = any(
            #     document.document_type == DocumentType.COMPROVATIVO_MORADA
            #     and document.status == DocumentStatus.APPROVED
            #     and document.expiration_date >= today
            #     for document in documents
            # )
    
            if not (has_valid_personal_document):
                raise ClientNotVerifiedError(
                    "Cliente precisa de ter um documento de identificação e um comprovativo de "
                    "morada aprovados e dentro da validade"
                )
    

    def submit(self, create_remittance : CreateRemittance) -> Remittance:

        client = self.client_repo.get_by_id(create_remittance.client_id)

        if not client:
            raise ResourceNotFoundError(f"Cliente com id {create_remittance.client_id} não encontrado")

        self._ensure_client_is_verified(create_remittance.client_id)

        if create_remittance.amount < MIN_AMOUNT:
            raise InvalidAmountError(f"O valor mínimo permitido por remessa é {MIN_AMOUNT}")

        if create_remittance.source_coin == create_remittance.target_coin:
            raise SameCurrencyError("A moeda de origem e a moeda de destino não podem ser iguais")

        if create_remittance.source_coin != AllowedCoins.EUR or create_remittance.target_coin != AllowedCoins.AOA:
            raise SourceCurrencyError("De momento só é permitido o envio de Euro (EUR) para Kwanza (AOA)")

        service_fee_amount = calculate_service_fee_amount(create_remittance.amount, SERVICE_FEE_RATE)
        amount_converted = calculate_amount_converted(create_remittance.amount, EXCHANGE_RATE, service_fee_amount)

        remittance = Remittance(
            **create_remittance.model_dump(),
            service_fee_rate=SERVICE_FEE_RATE,
            service_fee_amount=service_fee_amount,
            exchange_rate=EXCHANGE_RATE,
            amount_converted=amount_converted,
        )

        return self.remittance_repo.save(remittance)


    def _transition_status(self, remittance_id : str, new_status : RemittanceStatus):

        remittance = self._get_or_raise(remittance_id)

        message = {
            RemittanceStatus.SENT : 'enviada',
            RemittanceStatus.REJECTED: 'rejeitada'
        }
        
        if remittance.status != RemittanceStatus.IN_PROGRESS:
            raise InvalidRemittanceStatusError(
                f"Só é possível marcar como {message[new_status]} uma remessa em progresso "
                f"(estado atual: {remittance.status.value})"
            )
        remittance.status = new_status
        remittance.updated_at = datetime.now(timezone.utc)
        return remittance
       

    def mark_as_sent(self, remittance_id : str) -> Remittance:

        remittance = self._transition_status(remittance_id, RemittanceStatus.SENT)
        return self.remittance_repo.save(remittance)


    def mark_as_rejected(self, remittance_id : str):

        remittance = self._transition_status(remittance_id, RemittanceStatus.REJECTED)
        return self.remittance_repo.save(remittance)


    def get_remittance_by_id(self, remittance_id : str):
        return self._get_or_raise(remittance_id)

    def get_all(self, filter : RemittanceFilterParams):
        remittances = self.remittance_repo.get_all(
            limit=filter.limit,
            offset=filter.offset,
            order_by=filter.order_by,
            client_id=filter.client_id,
            status=filter.status,
            created_from=filter.created_from,
            created_to=filter.created_to,
        )
        total = self.remittance_repo.count(
            client_id=filter.client_id,
            status=filter.status,
            created_from=filter.created_from,
            created_to=filter.created_to,
        )

        return remittances, total


    def _get_or_raise(self, remittance_id : str) -> Remittance:

        remittance = self.remittance_repo.get_by_id(self._parse_id(remittance_id))

        if not remittance:
            raise ResourceNotFoundError(f"Remessa com id {remittance_id} não encontrada")

        return remittance


    @staticmethod
    def _parse_id(remittance_id : str) -> UUID:
        try:
            return UUID(str(remittance_id))
        except (ValueError, AttributeError, TypeError):
            raise InvalidIdentifierError(f"'{remittance_id}' não é um identificador válido")

