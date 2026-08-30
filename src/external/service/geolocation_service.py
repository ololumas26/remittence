import os

import geoip2.database
from geoip2.errors import AddressNotFoundError
from dotenv import load_dotenv

load_dotenv()

# Caminho para a base de dados local MaxMind GeoLite2 (ficheiro .mmdb).
# Não vem incluída no repositório (é preciso criar uma conta gratuita em
# https://www.maxmind.com/en/geolite2/signup, gerar uma license key, e
# descarregar o ficheiro "GeoLite2-Country" a partir daí).
GEOIP_DB_PATH = os.environ.get("GEOIP_DB_PATH", "geoip/GeoLite2-Country.mmdb")

# IPs privados/reservados (localhost, redes internas, testes) não têm país
# associado no GeoLite2 — em vez de bloquear, tratamos como "sem restrição"
# para não impedir desenvolvimento/testes locais.
_PRIVATE_IP_PREFIXES = ("127.", "10.", "192.168.", "::1")


class GeolocationService:
    """
    Fina camada sobre a base de dados local MaxMind GeoLite2 (Country) para
    resolver o país de um endereço IP, sem depender de nenhuma API externa
    em tempo de execução.
    """

    def __init__(self, db_path: str = GEOIP_DB_PATH):
        self.db_path = db_path
        self._reader: geoip2.database.Reader | None = None

    def _get_reader(self) -> geoip2.database.Reader:
        # Abre o ficheiro só na primeira utilização (evita rebentar a app no
        # arranque se o ficheiro ainda não tiver sido descarregado).
        if self._reader is None:
            self._reader = geoip2.database.Reader(self.db_path)
        return self._reader

    def get_country_code(self, ip_address: str) -> str | None:
        """
        Devolve o código do país (ISO 3166-1 alpha-2, ex: "AO", "PT") do IP
        indicado, ou None se o IP for privado/reservado ou não estiver
        mapeado na base de dados.
        """
        if not ip_address or ip_address.startswith(_PRIVATE_IP_PREFIXES):
            return None

        try:
            response = self._get_reader().country(ip_address)
        except AddressNotFoundError:
            return None

        return response.country.iso_code
