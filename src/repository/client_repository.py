from src.model.repo.client_repo import ClientRepository
from sqlmodel import Session, select, func
from src.model.client import Client
from uuid import UUID


class SqlClientRepository():

    def __init__(self, db : Session):
        self.db = db

    def get_by_email(self, email : str):
        return self.db.exec(select(Client).where(Client.email == email)).first()


    def get_by_id(self, client_id : str):
        return self.db.exec(select(Client).where(Client.id == client_id)).first()


    def get_by_auth_user_id(self, auth_user_id):
        return self.db.exec(select(Client).where(Client.auth_user_id == auth_user_id)).first()


    def get_all(self, limit : int, offset : int, order_by : str):
        order_column = getattr(Client, order_by)
        statement = select(Client).order_by(order_column).limit(limit).offset(offset)
        return self.db.exec(statement).all()


    def count(self) -> int:
        return self.db.exec(select(func.count()).select_from(Client)).one()


    def delete(self, client : Client):
        self.db.delete(client)
        self.db.commit()


    def save(self, client: Client):

        self.db.add(client)
        self.db.commit()
        self.db.refresh(client)

        return client
