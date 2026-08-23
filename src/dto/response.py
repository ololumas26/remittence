from typing import Any, Optional


def success_response(data: Any = None, message: Optional[str] = None) -> dict:
    """Envelope padrão para respostas de sucesso: `data` vem sempre presente,
    `message` só é incluído quando fizer sentido (ex: rotas de criação)."""

    response: dict = {"data": data}

    if message is not None:
        response["message"] = message

    return response


def paginated_response(data: Any, total: int, limit: int, offset: int) -> dict:
    """Envelope de sucesso para rotas de listagem: a paginação vive num
    campo à parte, irmão de `data`, não aninhada dentro dele."""

    return {
        "data": data,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


def error_response(error: str, message: str) -> dict:
    """Envelope padrão para respostas de erro: sem `data`, com um código
    estável em `error` e uma mensagem autoexplicativa em `message`."""

    return {"error": error, "message": message}
