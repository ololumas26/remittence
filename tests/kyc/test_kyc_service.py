"""
KycService decide o que conta como "cliente verificado" (usado por
RemittanceService para bloquear remessas, ver test_remittance_transition_idempotency.py
para esse lado) e monta o estado agregado exposto em GET /client/me/kyc-status.

Usa um fake em memória para o repositório de documentos — sem tocar na base de
dados real, mesmo padrão de FakeRemittanceRepo em tests/remittance/.
"""

from datetime import timedelta
from uuid import uuid4

from src.service.kyc_service import KycService
from src.service.age_calculator import get_current_date
from src.model.document import Document, DocumentType, DocumentStatus
from src.dto.kyc_dto import KycStatus

# Import "silencioso" só para registar as classes de relationship de Client
# (Recipient, Remittance, Payment) antes de qualquer instância de Document ser
# criada — sem isto, o SQLAlchemy falha a configurar o mapper de Client por não
# conseguir resolver esses nomes (strings de forward-reference). Ver o mesmo
# efeito, sem precisar disto, em test_remittance_transition_idempotency.py, que
# importa RemittanceService e arrasta o grafo todo de modelos como efeito colateral.
from src.model import client as _client_model, recipient as _recipient_model  # noqa: F401
from src.model import remittance as _remittance_model, payment as _payment_model  # noqa: F401


class FakeDocumentRepo:
    def __init__(self, documents: list[Document]):
        self._documents = documents

    def get_by_client_id(self, client_id):
        return self._documents


def make_document(
    document_type=DocumentType.BI,
    status=DocumentStatus.APPROVED,
    expiration_date=None,
) -> Document:
    return Document(
        id=uuid4(),
        client_id=uuid4(),
        document_number=str(uuid4())[:15],
        document_type=document_type,
        status=status,
        expiration_date=expiration_date or (get_current_date() + timedelta(days=365)),
    )


def make_service(documents: list[Document]) -> KycService:
    return KycService(FakeDocumentRepo(documents))


class TestKycServiceStatus:

    def test_sem_documentos_e_missing_documents_e_nao_verificado(self):
        service = make_service([])
        status = service.get_status(uuid4())

        assert status.status == KycStatus.MISSING_DOCUMENTS
        assert status.verified is False

    def test_documento_pessoal_aprovado_e_valido_e_approved_e_verificado(self):
        document = make_document(status=DocumentStatus.APPROVED)
        service = make_service([document])
        status = service.get_status(uuid4())

        assert status.status == KycStatus.APPROVED
        assert status.verified is True

    def test_documento_pessoal_pendente_e_pending_e_nao_verificado(self):
        document = make_document(status=DocumentStatus.PENDING)
        service = make_service([document])
        status = service.get_status(uuid4())

        assert status.status == KycStatus.PENDING
        assert status.verified is False

    def test_documento_pessoal_rejeitado_e_rejected_e_nao_verificado(self):
        document = make_document(status=DocumentStatus.REJECTED)
        service = make_service([document])
        status = service.get_status(uuid4())

        assert status.status == KycStatus.REJECTED
        assert status.verified is False

    def test_documento_pessoal_aprovado_mas_expirado_e_expired_e_nao_verificado(self):
        document = make_document(
            status=DocumentStatus.APPROVED,
            expiration_date=get_current_date() - timedelta(days=1),
        )
        service = make_service([document])
        status = service.get_status(uuid4())

        assert status.status == KycStatus.EXPIRED
        assert status.verified is False

    def test_um_documento_rejeitado_e_outro_aprovado_e_valido_conta_como_approved(self):
        rejected = make_document(document_type=DocumentType.PASSAPORTE, status=DocumentStatus.REJECTED)
        approved = make_document(document_type=DocumentType.BI, status=DocumentStatus.APPROVED)
        service = make_service([rejected, approved])
        status = service.get_status(uuid4())

        assert status.status == KycStatus.APPROVED
        assert status.verified is True
        assert len(status.documents) == 2

    def test_so_comprovativo_de_morada_nao_conta_como_documento_pessoal(self):
        # Comprovativo de morada não é exigido atualmente (ver TODO em kyc_service.py)
        # e não entra na lista de tipos "pessoais" que decidem o estado agregado.
        address_document = make_document(
            document_type=DocumentType.COMPROVATIVO_MORADA,
            status=DocumentStatus.APPROVED,
        )
        service = make_service([address_document])
        status = service.get_status(uuid4())

        assert status.status == KycStatus.MISSING_DOCUMENTS
        assert status.verified is False


class TestKycServiceIsVerified:

    def test_is_verified_espelha_o_campo_verified_de_get_status(self):
        document = make_document(status=DocumentStatus.APPROVED)
        service = make_service([document])
        client_id = uuid4()

        assert service.is_verified(client_id) == service.get_status(client_id).verified
