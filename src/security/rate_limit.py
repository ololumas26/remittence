from slowapi import Limiter
from slowapi.util import get_remote_address


# Limitador em memória (por processo) — suficiente para uma única instância.
# Se a app escalar para vários workers/processos/instâncias, isto deixa de
# ser partilhado entre eles e passa a ser preciso um backend Redis (a
# biblioteca slowapi/limits suporta isso via storage_uri, sem mudar os
# decorators @limiter.limit(...) espalhados pelos controllers).
limiter = Limiter(key_func=get_remote_address)
