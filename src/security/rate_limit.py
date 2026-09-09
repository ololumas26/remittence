from slowapi import Limiter
from slowapi.util import get_remote_address
import os


# Em produção, configurar REDIS_URL para partilhar limites entre workers/instâncias.
# O fallback em memória mantém o desenvolvimento local funcional.
app_env = os.environ.get("APP_ENV", "development").lower()
redis_url = os.environ.get("REDIS_URL", "").strip()
if app_env == "production" and not redis_url:
    raise RuntimeError("REDIS_URL é obrigatório em produção para o rate limiting partilhado")

storage_uri = redis_url or "memory://"
limiter = Limiter(key_func=get_remote_address, storage_uri=storage_uri)
