

class AppException(Exception):
    code: str = "INTERNAL_ERROR"


class UnderageClientError(AppException, ValueError):
    """Levantada quando um cliente não atinge a idade mínima exigida."""
    code = "CLIENT_UNDERAGE"


class ResourceAlreadyExistsError(AppException):
    code = "RESOURCE_ALREADY_EXISTS"


class ResourceNotFoundError(AppException):
    code = "RESOURCE_NOT_FOUND"


class InvalidIdentifierError(AppException):
    """Levantada quando um identificador recebido (ex: id na URL) não tem um formato válido."""
    code = "INVALID_IDENTIFIER"


class ExpiredDocumentError(AppException):
    """Levantada quando um documento é submetido já com a data de expiração no passado."""
    code = "DOCUMENT_EXPIRED"


class FileUploadError(AppException):
    """Levantada quando o upload de um ficheiro para o storage externo (Supabase) falha."""
    code = "FILE_UPLOAD_FAILED"


class DocumentNotEditableError(AppException):
    """Levantada quando se tenta atualizar um documento que não está expirado nem rejeitado."""
    code = "DOCUMENT_NOT_EDITABLE"


class DocumentNotDeletableError(AppException):
    """Levantada quando se tenta apagar um documento que já foi avaliado (aprovado ou rejeitado)."""
    code = "DOCUMENT_NOT_DELETABLE"
