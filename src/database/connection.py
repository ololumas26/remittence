from dotenv import load_dotenv
import os

load_dotenv()

APP_ENV = os.environ.get("APP_ENV", "development")
RAW_DATABASE_URL = os.environ.get("DATABASE_URL", "")

if APP_ENV == "production" and not RAW_DATABASE_URL:
    # Falha já no arranque, em vez de deixar a app subir "a funcionar" contra
    # o SQLite local por omissão sem ninguém dar por isso em produção.
    raise RuntimeError(
        "DATABASE_URL é obrigatória quando APP_ENV=production — define-a no "
        ".env de produção antes de arrancar a aplicação."
    )

DATASBASE_URL = RAW_DATABASE_URL or "sqlite:///remittance.db"

def get_connection() -> str:
    connection = DATASBASE_URL
    return connection