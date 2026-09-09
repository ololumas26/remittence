from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends
from src.constant.app_constant import APP_PREFIX
from src.supabase.server import client


# Esquema OAuth2 (fluxo "password") usado para proteger rotas.
#
# tokenUrl aponta para a rota de login já existente (POST /api/v1/auth/login)
# — é só isso que o OAuth2PasswordBearer precisa para saber onde o token é
# obtido; ele não chama essa rota nem sabe nada sobre Supabase, é só
# metadata usada pelo Swagger UI para mostrar o botão "Authorize" com um
# formulário de login, e para o FastAPI extrair o header
# "Authorization: Bearer <token>" do pedido.
#
# Este ficheiro só define o esquema — ainda não está ligado a nenhuma rota
# nem dependency.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{APP_PREFIX}/auth/login")

def get_user(token : str = Depends(oauth2_scheme)):

    user = client.auth.get_user(token)
    # Nunca registar o objeto User nem o token: podem conter PII e credenciais.
