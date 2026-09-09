from datetime import date
from decimal import Decimal

from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from src.model.client import Client
from src.model.document import Document  # noqa: F401
from src.model.notification import Notification, NotificationType
from src.model.payment import Payment  # noqa: F401
from src.model.recipient import Recipient  # noqa: F401
from src.model.remittance import AllowedCoins, Remittance
from src.repository.remittance_repository import SqlRemittanceRepository


def test_saves_remittance_before_notification_inside_the_same_transaction():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        client = Client(
            name="Cliente Teste",
            email="notification@example.com",
            birth_date=date(1990, 1, 1),
        )
        session.add(client)
        session.commit()

        remittance = Remittance(
            client_id=client.id,
            service_fee_rate=Decimal("0.05"),
            amount=Decimal("200.00"),
            amount_converted=Decimal("247000.00"),
            source_coin=AllowedCoins.EUR,
            target_coin=AllowedCoins.AOA,
            service_fee_amount=Decimal("10.00"),
            exchange_rate=Decimal("1300.00"),
            recipient_name="Ferreira Antonio",
            recipient_account_iban="AO06000600000100000000123",
        )
        notification = Notification(
            client_id=client.id,
            remittance_id=remittance.id,
            type=NotificationType.REMITTANCE_CREATED,
            title="Remessa criada",
            message="Mensagem",
        )

        SqlRemittanceRepository(session).save_with_notification(remittance, notification)

        assert session.exec(select(Remittance)).one().id == remittance.id
        assert session.exec(select(Notification)).one().remittance_id == remittance.id
