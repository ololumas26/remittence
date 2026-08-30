

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


class ClientNotVerifiedError(AppException):
    """Levantada quando o cliente tenta submeter uma remessa sem ter documentos de KYC aprovados e válidos."""
    code = "CLIENT_NOT_VERIFIED"


class InvalidAmountError(AppException):
    """Levantada quando o valor da remessa é inferior ao mínimo permitido."""
    code = "INVALID_AMOUNT"


class SameCurrencyError(AppException):
    """Levantada quando a moeda de origem e de destino da remessa são iguais."""
    code = "SAME_CURRENCY"

class SourceCurrencyError(AppException):
    """Levantada quando o corredor de moedas pedido não é o único atualmente suportado (EUR -> AOA)."""
    code = "SOURCE_CURRENCY"


class InvalidRemittanceStatusError(AppException):
    """Levantada quando se tenta transitar uma remessa para um estado a partir de um estado atual inválido
    (ex: marcar como enviada uma remessa que já foi enviada ou que foi rejeitada)."""
    code = "INVALID_REMITTANCE_STATUS"


class AuthenticationError(AppException):
    """Levantada quando a autenticação falha: token em falta/inválido/expirado, ou credenciais erradas
    no login/signup."""
    code = "AUTHENTICATION_FAILED"


class RestrictedRegionError(AppException):
    """Levantada quando uma remessa é submetida a partir de um IP cujo país não está na lista de
    países permitidos (ver ALLOWED_COUNTRIES)."""
    code = "RESTRICTED_REGION"


class AuthorizationError(AppException):
    """Levantada quando o utilizador está autenticado mas não tem o papel/permissão necessária
    para a operação (ex: rota exclusiva de staff acedida por uma conta sem esse papel).
    Distinta de AuthenticationError, que é para quando nem sequer há um utilizador válido."""
    code = "AUTHORIZATION_FAILED"
