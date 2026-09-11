"""Testes de DocumentService.reject — a rejeição de um documento exige sempre uma
justificação (note), guardada no próprio documento (ver document_service.py e
RejectDocument em document_dto.py para a validação do payload)."""

# Importações "silenciosas": garantem que todos os modelos com Relationship entre si já
# foram registados antes de instanciarmos um Document, ou o SQLAlchemy falha a resolver as
# referências (mesmo padrão usado nos outros testes de document/kyc).
import src.model.client  # noqa: F401
import src.model.recipient  # noqa: F401
import src.model.remittance  # noqa: F401
import src.model.payment  # noqa: F401

import pytest
from uuid import uuid4
from datetime import date, datetime, timezone

from pydantic import ValidationError

from src.model.document import Document, DocumentType, DocumentStatus
from src.dto.document_dto import RejectDocument
from src.service.document_service import DocumentService
from src.exception.exceptions import InvalidDocumentStatusError, ResourceNotFoundError


class FakeDocumentRepo:
    def __init__(self, documents=None):
        self._documents = {d.id: d for d in (documents or [])}

    def get_by_id(self, document_id):
        return self._documents.get(document_id)

    def save(self, document):
        self._documents[document.id] = document
        return document


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


def make_service(documents=None):
    document_repo = FakeDocumentRepo(documents)
    service = DocumentService(
        document_repository=document_repo,
        client_repository=None,
        file_storage_service=None,
    )
    return service, document_repo


class TestRejectDocumentDto:

    def test_rejeita_nota_em_branco(self):
        with pytest.raises(ValidationError):
            RejectDocument(note="   ")

    def test_rejeita_nota_demasiado_curta(self):
        with pytest.raises(ValidationError):
            RejectDocument(note="ab")

    def test_aceita_nota_valida(self):
        dto = RejectDocument(note="Foto ilegível")
        assert dto.note == "Foto ilegível"


class TestReject:

    def test_rejeita_documento_pendente_e_grava_o_motivo(self):
        document = make_document()
        service, _ = make_service([document])

        rejected = service.reject(str(document.id), note="Foto ilegível")

        assert rejected.status == DocumentStatus.REJECTED
        assert rejected.note == "Foto ilegível"

    def test_nao_permite_rejeitar_documento_que_nao_esta_pendente(self):
        document = make_document(status=DocumentStatus.APPROVED)
        service, _ = make_service([document])

        with pytest.raises(InvalidDocumentStatusError):
            service.reject(str(document.id), note="Motivo qualquer")

    def test_levanta_erro_quando_documento_nao_existe(self):
        service, _ = make_service([])

        with pytest.raises(ResourceNotFoundError):
            service.reject(str(uuid4()), note="Motivo qualquer")
