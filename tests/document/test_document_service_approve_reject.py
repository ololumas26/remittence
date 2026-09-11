"""Testes de DocumentService.approve/reject — transição de estado, nota de rejeição
obrigatória, notificação in-app e email best-effort (ver document_service.py e
notification_service.py's for_document_approved/for_document_rejected)."""

# Importações "silenciosas": garantem que todos os modelos com Relationship entre si já
# foram registados antes de instanciarmos um Document, ou o SQLAlchemy falha a resolver as
# referências (ver tests/kyc/test_kyc_service.py para o mesmo problema).
import src.model.client  # noqa: F401
import src.model.recipient  # noqa: F401
import src.model.remittance  # noqa: F401
import src.model.payment  # noqa: F401

import pytest
from types import SimpleNamespace
from uuid import uuid4
from datetime import date, datetime, timezone

from src.model.document import Document, DocumentType, DocumentStatus
from src.model.notification import NotificationType
from src.service.document_service import DocumentService
from src.exception.exceptions import InvalidDocumentStatusError, ResourceNotFoundError


class FakeDocumentRepo:
    def __init__(self, documents=None):
        self._documents = {d.id: d for d in (documents or [])}
        self.save_with_notification_calls = []

    def get_by_id(self, document_id):
        return self._documents.get(document_id)

    def save_with_notification(self, document, notification):
        self.save_with_notification_calls.append((document, notification))
        self._documents[document.id] = document
        return document


class FakeClientRepo:
    def __init__(self, client=None):
        self._client = client

    def get_by_id(self, client_id):
        return self._client


class FakeEmailService:
    def __init__(self):
        self.calls = []

    def send(self, to, subject, html):
        self.calls.append((to, subject, html))


class RaisingEmailService:
    """Simula uma falha inesperada a montar/enviar o email — approve()/reject() não podem
    deixar essa falha propagar depois de o documento já ter sido guardado."""

    def send(self, to, subject, html):
        raise RuntimeError("falha simulada no envio de email")


def make_document(**overrides):
    defaults = dict(
        id=uuid4(),
        client_id=uuid4(),
        document_number=str(uuid4())[:10],
        is_expired=False,
        document_type=DocumentType.BI,
        expiration_date=date(2099, 1, 1),
        file_path="https://example.supabase.co/storage/v1/object/product_images/abc/doc.png",
        status=DocumentStatus.PENDING,
        note=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Document(**defaults)


def make_service(documents=None, client=None, email_service=None):
    document_repo = FakeDocumentRepo(documents)
    client_repo = FakeClientRepo(client or SimpleNamespace(id=uuid4(), name="Cliente Teste"))
    email_service = email_service if email_service is not None else FakeEmailService()
    service = DocumentService(
        document_repository=document_repo,
        client_repository=client_repo,
        file_storage_service=None,
        email_service=email_service,
    )
    return service, document_repo, email_service


class TestApprove:

    def test_aprova_documento_pendente(self):
        document = make_document()
        service, repo, _ = make_service([document])

        approved = service.approve(str(document.id))

        assert approved.status == DocumentStatus.APPROVED

    def test_grava_notificacao_de_aprovacao(self):
        document = make_document()
        service, repo, _ = make_service([document])

        service.approve(str(document.id))

        assert len(repo.save_with_notification_calls) == 1
        saved_document, notification = repo.save_with_notification_calls[0]
        assert saved_document.id == document.id
        assert notification.client_id == document.client_id
        assert notification.document_id == document.id
        assert notification.type == NotificationType.DOCUMENT_APPROVED
        assert document.document_type.value in notification.message

    def test_envia_email_de_aprovacao_para_o_endereco_de_teste(self):
        document = make_document()
        service, _, email_service = make_service([document])

        service.approve(str(document.id))

        assert len(email_service.calls) == 1
        to, subject, html = email_service.calls[0]
        assert to == 'ololumas26@gmail.com'
        assert document.document_type.value in subject
        assert document.document_number in html

    def test_falha_a_enviar_email_nao_impede_a_aprovacao(self):
        document = make_document()
        service, repo, _ = make_service([document], email_service=RaisingEmailService())

        approved = service.approve(str(document.id))

        assert approved.status == DocumentStatus.APPROVED
        assert len(repo.save_with_notification_calls) == 1

    def test_nao_permite_aprovar_documento_que_nao_esta_pendente(self):
        document = make_document(status=DocumentStatus.REJECTED)
        service, _, _ = make_service([document])

        with pytest.raises(InvalidDocumentStatusError):
            service.approve(str(document.id))

    def test_levanta_erro_quando_documento_nao_existe(self):
        service, _, _ = make_service([])

        with pytest.raises(ResourceNotFoundError):
            service.approve(str(uuid4()))


class TestReject:

    def test_rejeita_documento_pendente_e_grava_o_motivo(self):
        document = make_document()
        service, _, _ = make_service([document])

        rejected = service.reject(str(document.id), note="Foto ilegível")

        assert rejected.status == DocumentStatus.REJECTED
        assert rejected.note == "Foto ilegível"

    def test_grava_notificacao_de_rejeicao_com_o_motivo(self):
        document = make_document()
        service, repo, _ = make_service([document])

        service.reject(str(document.id), note="Foto ilegível")

        assert len(repo.save_with_notification_calls) == 1
        saved_document, notification = repo.save_with_notification_calls[0]
        assert notification.client_id == document.client_id
        assert notification.document_id == document.id
        assert notification.type == NotificationType.DOCUMENT_REJECTED
        assert "Foto ilegível" in notification.message

    def test_envia_email_de_rejeicao_com_o_motivo_para_o_endereco_de_teste(self):
        document = make_document()
        service, _, email_service = make_service([document])

        service.reject(str(document.id), note="Foto ilegível")

        assert len(email_service.calls) == 1
        to, subject, html = email_service.calls[0]
        assert to == 'ololumas26@gmail.com'
        assert document.document_type.value in subject
        assert "Foto ilegível" in html

    def test_falha_a_enviar_email_nao_impede_a_rejeicao(self):
        document = make_document()
        service, repo, _ = make_service([document], email_service=RaisingEmailService())

        rejected = service.reject(str(document.id), note="Foto ilegível")

        assert rejected.status == DocumentStatus.REJECTED
        assert len(repo.save_with_notification_calls) == 1

    def test_nao_permite_rejeitar_documento_que_nao_esta_pendente(self):
        document = make_document(status=DocumentStatus.APPROVED)
        service, _, _ = make_service([document])

        with pytest.raises(InvalidDocumentStatusError):
            service.reject(str(document.id), note="Motivo qualquer")
