from sqlmodel import SQLModel, Session, create_engine
from src.database.connection import get_connection
from fastapi import Depends
from typing import Annotated


DATABASE_URL = get_connection()
engine = create_engine(DATABASE_URL)


def get_db_session():
    with Session(engine) as session:
        yield session


session_DP = Annotated[Session, Depends(get_db_session)]