from dotenv import load_dotenv
import os

load_dotenv()

DATASBASE_URL = os.environ.get("DATABASE_URL", "sqlite:///remittance.db")

def get_connection() -> str:
    connection = DATASBASE_URL
    return connection