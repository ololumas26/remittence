"""Testes de DocumentService.get_signed_url — link assinado e de curta duração para o
ficheiro de um documento (nunca o file_path em bruto, ver file_storage_repo.py)."""

# Importações "silenciosas": garantem que todos os modelos com Relationship entre si já
# foram registados antes de instanciarmos um Document, ou o SQLAlchemy falha a resolver as
# referências (ver tests/kyc/test_kyc_service.py para o mesmo problema).
import src.model.client  # noqa: F401
import src.model.recipient  # noqa: F401
import src.model.remittance  # noqa: F401
import src.model.payment  # noqa: F401

import pytest
from uuid import uuid4
from datetime import date, datetime, timezone

from src.model.document import Document, DocumentType, DocumentStatus
from src.service.document_service import DocumentService
from src.exception.exceptions import ResourceNotFoundError


class FakeDocumentRepo:
    def __init__(self, documents=None):
        self._documents = {d.id: d for d in (documents or [])}

    def get_by_id(self, document_id):
        return self._documents.get(document_id)

    def get_by_document_number(self, document_number):
        return None

    def get_all(self, limit, offset, order_by, client_id=None):
        return list(self._documents.values())

    def count(self, client_id=None):
        return len(self._documents)

    def get_by_client_id(self, client_id):
        return [d for d in self._documents.values() if d.client_id == client_id]

    def save(self, document):
        self._documents[document.id] = document
        return document

    def delete(self, document):
        self._documents.pop(document.id, None)


class FakeFileStorageService:
    def __init__(self, signed_url="https://example.supabase.co/storage/v1/object/sign/product_images/x?token=abc"):
        self.signed_url = signed_url
        self.calls = []

    def get_signed_url(self, file_path, expires_in=300):
        self.calls.append((file_path, expires_in))
        return self.signed_url


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
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Document(**defaults)


def make_service(documents=None, file_storage_service=None):
    document_repo = FakeDocumentRepo(documents)
    file_storage_service = file_storage_service or FakeFileStorageService()
    return DocumentService(
        document_repository=document_repo,
        client_repository=None,
        file_storage_service=file_storage_service,
        email_service=None,
    ), file_storage_service


class TestDocumentServiceGetSignedUrl:

    def test_returns_signed_url_for_existing_document_with_file(self):
        document = make_document()
        service, file_storage_service = make_service([document])

        url = service.get_signed_url(str(document.id), expires_in=300)

        assert url == file_storage_service.signed_url
        assert file_storage_service.calls == [(document.file_path, 300)]

    def test_uses_default_expiration_when_not_specified(self):
        document = make_document()
        service, file_storage_service = make_service([document])

        service.get_signed_url(str(document.id))

        assert file_storage_service.calls[0][1] == 300

    def test_raises_when_document_does_not_exist(self):
        service, _ = make_service([])

        with pytest.raises(ResourceNotFoundError):
            service.get_signed_url(str(uuid4()))

    def test_raises_when_document_has_no_file(self):
        document = make_document(file_path=None)
        service, file_storage_service = make_service([document])

        with pytest.raises(ResourceNotFoundError):
            service.get_signed_url(str(document.id))

        assert file_storage_service.calls == []
