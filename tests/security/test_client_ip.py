"""Testes de get_client_ip — o IP daqui alimenta a chave do rate limiter E o bloqueio
geográfico em RemittanceService._ensure_allowed_region, por isso confiar cegamente no
X-Forwarded-For (que o próprio cliente controla) seria uma forma trivial de contornar as duas
proteções. Ver o docstring de get_client_ip em src/security/client_ip.py para o raciocínio
completo."""

from types import SimpleNamespace

from src.security.client_ip import get_client_ip


def make_request(direct_ip: str | None, forwarded_for: str | None = None):
    """Fake mínimo de fastapi.Request — só o que get_client_ip lê (.client.host e
    .headers.get)."""
    headers = {"X-Forwarded-For": forwarded_for} if forwarded_for is not None else {}
    client = SimpleNamespace(host=direct_ip) if direct_ip is not None else None
    return SimpleNamespace(client=client, headers=headers)


class TestSemProxyDeConfianca:
    """TRUSTED_PROXY_IPS vazio (o default) — X-Forwarded-For nunca é confiado, mesmo que o
    pedido o traga."""

    def test_ignora_x_forwarded_for_e_usa_o_ip_direto(self, monkeypatch):
        monkeypatch.delenv("TRUSTED_PROXY_IPS", raising=False)
        request = make_request(direct_ip="203.0.113.9", forwarded_for="1.2.3.4")

        assert get_client_ip(request) == "203.0.113.9"

    def test_tentativa_de_spoof_do_bloqueio_geografico_nao_funciona(self, monkeypatch):
        # Sem proxy de confiança configurado, um cliente não consegue fingir vir de outro
        # país só enviando X-Forwarded-For — é exatamente o cenário que motivou este fix.
        monkeypatch.delenv("TRUSTED_PROXY_IPS", raising=False)
        request = make_request(direct_ip="198.51.100.7", forwarded_for="41.0.0.1")

        assert get_client_ip(request) == "198.51.100.7"

    def test_sem_client_devolve_string_vazia(self, monkeypatch):
        monkeypatch.delenv("TRUSTED_PROXY_IPS", raising=False)
        request = make_request(direct_ip=None)

        assert get_client_ip(request) == ""


class TestComProxyDeConfianca:

    def test_pedido_vindo_do_ip_exato_confia_no_x_forwarded_for(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.5")
        request = make_request(direct_ip="10.0.0.5", forwarded_for="41.0.0.1, 10.0.0.5")

        assert get_client_ip(request) == "41.0.0.1"

    def test_pedido_vindo_de_dentro_do_cidr_confia_no_x_forwarded_for(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_IPS", "173.245.48.0/20,103.21.244.0/22")
        request = make_request(direct_ip="173.245.50.10", forwarded_for="41.0.0.1")

        assert get_client_ip(request) == "41.0.0.1"

    def test_pedido_de_fora_da_lista_continua_a_ignorar_o_header(self, monkeypatch):
        # O ponto central do fix: só perguntar "quem enviou X-Forwarded-For" não chega — tem
        # de ser um dos proxies configurados, senão o header é descartado.
        monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.5")
        request = make_request(direct_ip="203.0.113.9", forwarded_for="41.0.0.1")

        assert get_client_ip(request) == "203.0.113.9"

    def test_sem_x_forwarded_for_usa_sempre_o_ip_direto(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.5")
        request = make_request(direct_ip="10.0.0.5", forwarded_for=None)

        assert get_client_ip(request) == "10.0.0.5"

    def test_entrada_invalida_em_trusted_proxy_ips_e_ignorada_sem_rebentar(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_IPS", "isto-nao-e-um-ip, 10.0.0.5")
        request = make_request(direct_ip="10.0.0.5", forwarded_for="41.0.0.1")

        assert get_client_ip(request) == "41.0.0.1"

    def test_so_o_primeiro_valor_da_cadeia_e_usado(self, monkeypatch):
        # O primeiro é sempre o cliente original; os seguintes são proxies intermédios.
        monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.5")
        request = make_request(direct_ip="10.0.0.5", forwarded_for="41.0.0.1, 9.9.9.9, 10.0.0.5")

        assert get_client_ip(request) == "41.0.0.1"
