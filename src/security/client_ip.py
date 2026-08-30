from fastapi import Request


def get_client_ip(request: Request) -> str:
    """
    Extrai o IP real do cliente que fez o pedido.

    Se a API estiver atrás de um proxy/load balancer (ex: em produção), o IP
    original vem no header X-Forwarded-For (o primeiro da lista — os
    seguintes são proxies intermédios). Sem proxy à frente (ex: em dev local),
    usamos diretamente request.client.host.

    Nota: X-Forwarded-For é um header que o próprio cliente pode enviar, por
    isso só deve ser confiado quando a API está mesmo atrás de um proxy de
    confiança que o sobrescreve (não se limita a acrescentar-lhe valores).
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.client.host if request.client else ""
