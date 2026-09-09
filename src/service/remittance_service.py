import logging

from src.model.repo.remittance_repo import RemittanceRepository
from src.model.repo.client_repo import ClientRepository
from src.model.repo.document_repo import DocumentRepository
from src.model.repo.recipient_repo import RecipientRepository
from src.model.repo.payment_repo import PaymentRepository
from src.model.payment import PaymentStatus
from src.dto.remittance_dto import CreateRemittance
from src.dto.filter import RemittanceFilterParams
from src.model.client import Client
from src.model.remittance import Remittance, AllowedCoins, RemittanceStatus
from src.model.document import DocumentType, DocumentStatus
from src.service.age_calculator import get_current_date, get_18_year_date
from src.service.exchange_calculator import calculate_service_fee_amount, calculate_amount_converted
from src.service.remittance_email_template import (
    remittance_created_subject,
    render_remittance_created_email,
    remittance_sent_subject,
    render_remittance_sent_email,
)
from src.external.service.geolocation_service import GeolocationService
from src.external.service.email_service import EmailService
from src.constant.app_constant import MIN_AMOUNT, MAX_AMOUNT, EXCHANGE_RATE, SERVICE_FEE_RATE, ALLOWED_COUNTRIES
from src.exception.exceptions import (
    ResourceNotFoundError,
    ClientNotVerifiedError,
    InvalidAmountError,
    SameCurrencyError,
    SourceCurrencyError,
    InvalidRemittanceStatusError,
    InvalidIdentifierError,
    RestrictedRegionError,
    UnderageClientError,
)
from uuid import UUID

logger = logging.getLogger("remittance")


# Documentos que servem como identificação pessoal — qualquer um destes, aprovado
# e ainda válido, conta pra verificação de KYC. O comprovativo de morada é à parte.
PERSONAL_DOCUMENT_TYPES = (DocumentType.BI, DocumentType.PASSAPORTE, DocumentType.TITULO_RESIDENCIA)


class RemittanceService:

    def __init__(self, remittance_repository : RemittanceRepository, client_repository : ClientRepository,
                 document_repository : DocumentRepository, recipient_repository : RecipientRepository,
                 geolocation_service : GeolocationService, email_service : EmailService,
                payment_repository : PaymentRepository):
        self.remittance_repo = remittance_repository
        self.client_repo = client_repository
        self.document_repo = document_repository
        self.recipient_repo = recipient_repository
        self.geolocation_service = geolocation_service
        self.email_service = email_service
        self.payment_repo = payment_repository

    def _ensure_client_is_adult(self, client) -> None:
        # ClientService.create/update já bloqueiam data de nascimento <18 anos ao gravar — mas
        # isso é o único ponto de controlo, e há dois caminhos que ainda podem produzir um
        # cliente com o registo "errado": um login com Google (que não dá data de nascimento,
        # ver AuthProvider "needs-profile") depende inteiramente da pessoa preencher esse campo
        # com verdade no ecrã de completar perfil, e alterações de perfil antigas/futuras podem
        # não ter passado pela mesma validação. Reverificar aqui, no momento mais sensível (uma
        # remessa de dinheiro a sair), é a rede de segurança final.
        if get_18_year_date(client.birth_date) > get_current_date():
            raise UnderageClientError("Apenas clientes com 18+ anos podem submeter remessas")


    def _ensure_client_is_verified(self, client_id : UUID) -> None:

            documents = self.document_repo.get_by_client_id(client_id)
            today = get_current_date()

            has_valid_personal_document = any(
                document.document_type in PERSONAL_DOCUMENT_TYPES
                and document.status == DocumentStatus.APPROVED
                and document.expiration_date >= today
                for document in documents
            )

            #TODO: Reativar apenas quando melhorar a questão da submissão do comprovativo de morada
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


    def _ensure_allowed_region(self, ip_address : str) -> None:
        # IPs privados/reservados (dev local, testes) devolvem None e não são
        # bloqueados — ver GeolocationService. Para qualquer IP público,
        # falha fechado: só passa se o país for identificado E permitido.
        country_code = self.geolocation_service.get_country_code(ip_address)

        if country_code is not None and country_code not in ALLOWED_COUNTRIES:
            raise RestrictedRegionError(
                "De momento só é possível submeter remessas a partir de Angola ou Portugal"
            )


    def _get_owned_recipient(self, recipient_id : UUID, client_id : UUID):
        # Mesma resposta de um id inexistente propositadamente — não confirmamos
        # a um cliente que um destinatário de outra pessoa existe.
        recipient = self.recipient_repo.get_by_id(recipient_id)

        if not recipient or recipient.client_id != client_id:
            raise ResourceNotFoundError(f"Destinatário com id {recipient_id} não encontrado")

        return recipient


    def build_remittance(self, create_remittance : CreateRemittance, ip_address : str = "") -> tuple[Remittance, Client]:
        """
        Faz toda a validação e constrói o Remittance em memória — sem o gravar. Separado de
        submit() para o PaymentService conseguir construir a remessa, entregá-la (ainda por
        gravar) ao PaymentTransactionRepository junto com o Payment, e deixar esse repositório
        gravar os dois numa única transação. submit() continua a existir tal como antes (grava
        sozinho) para a rota direta POST /remittance, que não passa por nenhum pagamento.
        """

        client = self.client_repo.get_by_id(create_remittance.client_id)

        if not client:
            raise ResourceNotFoundError(f"Cliente com id {create_remittance.client_id} não encontrado")

        recipient = self._get_owned_recipient(create_remittance.recipient_id, client.id)

        self._ensure_client_is_adult(client)

        self._ensure_client_is_verified(create_remittance.client_id)

        self._ensure_allowed_region(ip_address)

        if create_remittance.amount < MIN_AMOUNT:
            raise InvalidAmountError(f"O valor mínimo permitido por remessa é {MIN_AMOUNT}")

        if create_remittance.amount > MAX_AMOUNT:
            raise InvalidAmountError(f"O valor máximo permitido por remessa é {MAX_AMOUNT}")

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
            # Snapshot do destinatário no momento da submissão — continua correto
            # mesmo que o Recipient seja depois editado ou apagado.
            recipient_name=recipient.full_name,
            recipient_account_iban=recipient.account_iban,
            ip_address=ip_address or None,
        )

        return remittance, client


    def submit(self, create_remittance : CreateRemittance, ip_address : str = "") -> Remittance:

        remittance, client = self.build_remittance(create_remittance, ip_address)

        saved_remittance = self.remittance_repo.save(remittance)

        self.send_created_email(client, saved_remittance)

        return saved_remittance


    def send_created_email(self, client : Client, remittance : Remittance) -> None:
        # EmailService.send já não levanta exceção nenhuma (ver lá) — este try/except é só uma
        # segunda rede de segurança para uma falha imprevista a MONTAR o email (ex: um valor
        # None inesperado), para nunca deixar a submissão da remessa em si falhar por causa da
        # notificação por email.
        try:
            subject = remittance_created_subject(remittance)
            html = render_remittance_created_email(client.name, remittance)
            # TODO: SUBSTITUIR DEPOIS PARA O EMAIL DO CLIENTE QUANDO JÁ ESTIVER EM PRODUÇÃO
            self.email_service.send('ololumas26@gmail.com', subject, html)
        except Exception:
            logger.exception("Falha ao preparar o email de remessa criada para a remessa %s", remittance.id)


    def send_sent_email(self, client : Client, remittance : Remittance) -> None:
        # Mesma rede de segurança de send_created_email acima — uma falha a montar/enviar este
        # email nunca deve impedir mark_as_sent de ter marcado a remessa como enviada com sucesso.
        try:
            subject = remittance_sent_subject(remittance)
            html = render_remittance_sent_email(client.name, remittance)
            # TODO: SUBSTITUIR DEPOIS PARA O EMAIL DO CLIENTE QUANDO JÁ ESTIVER EM PRODUÇÃO
            self.email_service.send('ololumas26@gmail.com', subject, html)
        except Exception:
            logger.exception("Falha ao preparar o email de remessa enviada para a remessa %s", remittance.id)


    def _transition_status(self, remittance_id : str, new_status : RemittanceStatus) -> tuple[Remittance, bool]:
        """Devolve (remessa, transicionou_agora). `transicionou_agora` é False quando a remessa já
        estava no estado pretendido — dois membros do staff a marcar a mesma remessa como enviada
        (em simultâneo, ou um a repetir um pedido que já tinha sido aceite) não deve dar erro ao
        segundo: é a mesma transição, só que já feita. `mark_as_sent` usa o booleano para não
        reenviar o email de confirmação nesse caso."""

        remittance = self._get_or_raise(remittance_id)

        # Já está no estado pretendido — sucesso idempotente, sem repetir efeitos secundários.
        if remittance.status == new_status:
            return remittance, False

        payment = self.payment_repo.get_by_id(remittance.payment_id)

        if new_status == RemittanceStatus.SENT:
            if not payment or payment.status != PaymentStatus.SUCCEEDED:
                raise ResourceNotFoundError("Essa remessa ainda não foi paga, pelo que não pode ser marcada como enviada")

        message = {
            RemittanceStatus.SENT : 'enviada',
            RemittanceStatus.REJECTED: 'rejeitada'
        }

        if remittance.status != RemittanceStatus.IN_PROGRESS:
            # Estado terminal diferente do pretendido (ex: já rejeitada e agora tentam marcar como
            # enviada) — conflito real, não uma repetição inofensiva do mesmo pedido.
            raise InvalidRemittanceStatusError(
                f"Só é possível marcar como {message[new_status]} uma remessa em progresso "
                f"(estado atual: {remittance.status.value})"
            )
        # The reads above provide helpful errors; only the conditional UPDATE decides
        # whether this request wins. Do not mutate/save the earlier ORM snapshot.
        updated = self.remittance_repo.transition_status(remittance.id, new_status)
        if updated is None:
            # Perdemos a corrida: outro pedido já tratou disto entretanto. Vê o que aconteceu antes
            # de decidir se é o mesmo pedido a repetir-se (idempotente) ou um conflito real.
            current = self._get_or_raise(remittance_id)
            if current.status == new_status:
                return current, False
            raise InvalidRemittanceStatusError(
                "A remessa ou o pagamento foi alterado por outro pedido. Atualiza e tenta novamente."
            )
        return updated, True


    def mark_as_sent(self, remittance_id : str) -> Remittance:

        saved_remittance, did_transition = self._transition_status(remittance_id, RemittanceStatus.SENT)

        if not did_transition:
            return saved_remittance

        # _transition_status já confirmou que a remessa existe, mas não devolve o cliente — vamos
        # buscá-lo só agora, e só para o email (get_by_id devolve None em vez de levantar, mas
        # isto nunca deveria acontecer: uma remessa sempre teve um client_id válido na submissão).
        client = self.client_repo.get_by_id(saved_remittance.client_id)
        if client:
            self.send_sent_email(client, saved_remittance)
        else:
            logger.error(
                "Remessa %s marcada como enviada mas o cliente %s já não existe — email não enviado",
                saved_remittance.id, saved_remittance.client_id,
            )

        return saved_remittance


    def mark_as_rejected(self, remittance_id : str):

        saved_remittance, _ = self._transition_status(remittance_id, RemittanceStatus.REJECTED)
        return saved_remittance


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
