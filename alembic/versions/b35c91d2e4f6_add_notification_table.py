"""add notification table

Revision ID: b35c91d2e4f6
Revises: 24b268831668
Create Date: 2026-09-07 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "b35c91d2e4f6"
down_revision: Union[str, Sequence[str], None] = "24b268831668"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("remittance_id", sa.Uuid(), nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "REMITTANCE_CREATED",
                "REMITTANCE_SENT",
                "REMITTANCE_REJECTED",
                name="notificationtype",
            ),
            nullable=False,
        ),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["client.id"],
            name="fk_notification_client_id_client",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["remittance_id"],
            ["remittance.id"],
            name="fk_notification_remittance_id_remittance",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "remittance_id",
            "type",
            name="uq_notification_remittance_type",
        ),
    )
    op.create_index(
        "ix_notification_client_created_at",
        "notification",
        ["client_id", "created_at"],
    )
    op.create_index(
        "ix_notification_client_unread",
        "notification",
        ["client_id"],
        postgresql_where=sa.text("read_at IS NULL"),
        sqlite_where=sa.text("read_at IS NULL"),
    )
    op.create_index("ix_notification_remittance_id", "notification", ["remittance_id"])

    # O frontend não acede ao Data API diretamente; só a API FastAPI usa esta tabela através
    # da ligação Postgres do servidor. RLS protege-a caso o schema public esteja exposto.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE notification ENABLE ROW LEVEL SECURITY")
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    EXECUTE 'REVOKE ALL ON TABLE notification FROM anon';
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    EXECUTE 'REVOKE ALL ON TABLE notification FROM authenticated';
                END IF;
            END
            $$
            """
        )


def downgrade() -> None:
    op.drop_index("ix_notification_remittance_id", table_name="notification")
    op.drop_index("ix_notification_client_unread", table_name="notification")
    op.drop_index("ix_notification_client_created_at", table_name="notification")
    op.drop_table("notification")
