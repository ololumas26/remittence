from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import event
from src.database.connection import get_connection
from fastapi import Depends
from typing import Annotated


DATABASE_URL = get_connection()
engine = create_engine(DATABASE_URL or "sqlite:///remittance.db")

# O SQLite não aplica foreign keys (nem ON DELETE SET NULL/CASCADE) por
# omissão em cada ligação — ao contrário do Postgres (produção), onde isto
# é sempre garantido pela BD. Sem isto, em desenvolvimento local, apagar um
# client/recipient deixava remittance.client_id/recipient_id "pendurados"
# em vez de passarem a NULL como o modelo assume.
if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db_session():
    with Session(engine) as session:
        yield session


session_DP = Annotated[Session, Depends(get_db_session)]