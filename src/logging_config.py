import logging
import os


def configure_logging() -> None:
    """
    Logging estruturado mínimo: nível configurável via LOG_LEVEL e formato
    com timestamp/nível/logger, para as falhas em produção pelo menos
    aparecerem nos logs do processo em vez de desaparecerem em silêncio.
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
