from src.model.repo.recipient_repo import RecipientRepository
from src.model.repo.client_repo import ClientRepository
from src.dto.recipient_dto import CreateRecipient, UpdateRecipient
from src.dto.filter import RecipientFilterParams
from src.model.recipient import Recipient
from src.exception.exceptions import InvalidIdentifierError, InvalidRecipientBankError, ResourceNotFoundError
from src.validator.iban_validator import clean_iban, get_bank_code
from uuid import UUID
from datetime import datetime, timezone


class RecipientService:

    def __init__(self, recipient_repository : RecipientRepository, client_repository : ClientRepository):
        self.recipient_repo = recipient_repository
        self.client_repo = client_repository

    def create(self, create_recipient : CreateRecipient) -> Recipient:

        client = self.client_repo.get_by_id(create_recipient.client_id)

        if not client:
            raise ResourceNotFoundError(f"Cliente com id {create_recipient.client_id} não encontrado")

        recipient = Recipient(**create_recipient.model_dump())

        return self.recipient_repo.save(recipient)

    def update(self, recipient_id : str, update_recipient : UpdateRecipient) -> Recipient:

        recipient = self._get_or_raise(recipient_id)
        changes = update_recipient.model_dump(exclude_unset=True)

        resulting_iban = changes.get('account_iban', recipient.account_iban)
        resulting_bank_code = changes.get('bank_code', recipient.bank_code)
        if resulting_bank_code is not None and get_bank_code(clean_iban(resulting_iban)) != resulting_bank_code:
            raise InvalidRecipientBankError("O banco selecionado não corresponde ao IBAN")

        for key, value in changes.items():
            if value is not None:
                setattr(recipient, key, value)

        recipient.updated_at = datetime.now(timezone.utc)

        return self.recipient_repo.save(recipient)

    def delete(self, recipient_id : str) -> None:

        recipient = self._get_or_raise(recipient_id)
        self.recipient_repo.delete(recipient)

    def get_by_id(self, recipient_id : str) -> Recipient:
        return self._get_or_raise(recipient_id)

    def get_all(self, filter : RecipientFilterParams):
        recipients = self.recipient_repo.get_all(
            limit=filter.limit,
            offset=filter.offset,
            order_by=filter.order_by,
            client_id=filter.client_id,
        )
        total = self.recipient_repo.count(client_id=filter.client_id)

        return recipients, total

    def _get_or_raise(self, recipient_id : str) -> Recipient:
        recipient = self.recipient_repo.get_by_id(self._parse_id(recipient_id))

        if not recipient:
            raise ResourceNotFoundError(f"Destinatário com id {recipient_id} não encontrado")

        return recipient

    @staticmethod
    def _parse_id(recipient_id : str) -> UUID:
        try:
            return UUID(str(recipient_id))
        except (ValueError, AttributeError, TypeError):
            raise InvalidIdentifierError(f"'{recipient_id}' não é um identificador válido")
