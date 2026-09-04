from supabase import create_client, Client
import os
from dotenv import load_dotenv
from typing import Annotated

load_dotenv()

supabase_url = os.environ.get("SUPABASE_URL")
supbase_key = os.environ.get("SUPABASE_KEY")
supabase_service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

client : Client = create_client(supabase_url, supbase_key)

# Cliente com a service_role key: usado para operações de servidor que
# precisam de ignorar as RLS policies (ex: Storage) ou de acesso à Admin API
# (ex: apagar utilizadores no Auth), já que a autorização é garantida na
# nossa camada de serviço e não pelas policies/permissões do Supabase.
admin_client : Client = create_client(supabase_url, supabase_service_role_key)


        
        
    