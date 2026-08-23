

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
