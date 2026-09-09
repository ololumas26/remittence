"""add bank to recipient and remittance

Revision ID: c46da2e5f7a8
Revises: b35c91d2e4f6
Create Date: 2026-09-07 19:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "c46da2e5f7a8"
down_revision: Union[str, Sequence[str], None] = "b35c91d2e4f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VALID_BANK_CODES = ("0004", "0005", "0006", "0040", "0043", "0047", "0048", "0051", "0054", "0055", "0059", "0066", "0067")


def upgrade() -> None:
    with op.batch_alter_table("recipient", schema=None) as batch_op:
        batch_op.add_column(sa.Column("bank_code", sqlmodel.sql.sqltypes.AutoString(length=4), nullable=True))

    with op.batch_alter_table("remittance", schema=None) as batch_op:
        batch_op.add_column(sa.Column("recipient_bank_code", sqlmodel.sql.sqltypes.AutoString(length=4), nullable=True))

    # Recupera o banco de registos antigos a partir do IBAN angolano (AO06 + código bancário).
    codes = ", ".join(f"'{code}'" for code in VALID_BANK_CODES)
    op.execute(
        sa.text(
            f"UPDATE recipient SET bank_code = substr(replace(account_iban, ' ', ''), 5, 4) "
            f"WHERE substr(replace(account_iban, ' ', ''), 5, 4) IN ({codes})"
        )
    )
    op.execute(
        sa.text(
            f"UPDATE remittance SET recipient_bank_code = substr(replace(recipient_account_iban, ' ', ''), 5, 4) "
            f"WHERE substr(replace(recipient_account_iban, ' ', ''), 5, 4) IN ({codes})"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("remittance", schema=None) as batch_op:
        batch_op.drop_column("recipient_bank_code")
    with op.batch_alter_table("recipient", schema=None) as batch_op:
        batch_op.drop_column("bank_code")
