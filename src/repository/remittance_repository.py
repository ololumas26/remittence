from src.model.repo.remittance_repo import RemittanceRepository
from sqlmodel import Session, select
from src.model.remittance import Remittance
from uuid import UUID


class SqlRemittanceRepository():

    def __init__(self, db : Session):
        self.db = db

    def get_by_id(self, remittance_id : UUID):
        return self.db.exec(select(Remittance).where(Remittance.id == remittance_id)).first()

    def save(self, remittance : Remittance):

        self.db.add(remittance)
        self.db.commit()
        self.db.refresh(remittance)

        return remittance
