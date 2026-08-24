from supabase import create_client, Client
import os
from dotenv import load_dotenv
from typing import Annotated

load_dotenv()

supabase_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
supbase_key = os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")

client : Client = create_client(supabase_url, supbase_key)


        
        
    