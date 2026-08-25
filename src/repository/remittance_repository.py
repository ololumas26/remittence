from src.model.repo.remittance_repo import RemittanceRepository
from sqlmodel import Session
from src.model.remittance import Remittance


class SqlRemittanceRepository():

    def __init__(self, db : Session):
        self.db = db

    def save(self, remittance : Remittance):

        # self.db.add(remittance)
        # self.db.commit()
        # self.db.refresh(remittance)

        return remittance
