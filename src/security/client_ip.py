import ipaddress
import os

from fastapi import Request


def _parse_trusted_proxies(raw: str) -> tuple:
    networks = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            # Entrada mal formada em TRUSTED_PROXY_IPS — ignora-a em vez de rebentar o
            # arranque da app; fica só sem efeito (nunca é "mais permissiva" por engano).
            continue

    return tuple(networks)


def _is_trusted_proxy(ip: str) -> bool:
    if not ip:
        return False

    trusted_proxies_raw = os.environ.get("TRUSTED_PROXY_IPS", "")
    trusted_networks = _parse_trusted_proxies(trusted_proxies_raw)

    if not trusted_networks:
        return False

    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False

    return any(address in network for network in trusted_networks)


def get_client_ip(request: Request) -> str:
    """
    Extrai o IP real do cliente que fez o pedido — usado tanto para a chave do rate limiter
    como para o bloqueio geográfico em RemittanceService._ensure_allowed_region (só
    Angola/Portugal podem submeter remessas), por isso um IP errado aqui não é só um detalhe
    de log: é uma proteção real que se pode contornar.

    X-Forwarded-For é um header que o PRÓPRIO CLIENTE pode enviar — não prova nada sozinho.
    Só é seguro confiar nele quando sabemos que o pedido chegou mesmo através de um proxy de
    confiança (load balancer/CDN) que sobrescreve esse header em vez de só lhe acrescentar
    valores. Essa confiança nunca é assumida por omissão: só se aplica quando o IP que
    estabeleceu a ligação TCP direta (request.client.host) está na lista configurada em
    TRUSTED_PROXY_IPS (IPs/CIDRs separados por vírgula — ex: o range de IPs do teu load
    balancer/CDN em produção).

    Sem TRUSTED_PROXY_IPS configurado (ou com um pedido que não vem de lá), X-Forwarded-For é
    ignorado por completo e usamos sempre request.client.host — a única coisa que um cliente
    não consegue falsificar, mesmo que isso signifique que, atrás de um proxy não listado,
    todos os pedidos pareçam vir do mesmo IP (do próprio proxy). É a opção "falha fechado":
    pior para a granularidade do rate limit/geobloqueio do que confiar cegamente no header,
    mas nunca contornável só por um cliente escolher o que envia.
    """
    direct_ip = request.client.host if request.client else ""

    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for and _is_trusted_proxy(direct_ip):
        return forwarded_for.split(",")[0].strip()

    return direct_ip
