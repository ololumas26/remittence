"""add ip_address to remittance

Revision ID: c1a2f3b4d5e6
Revises: a084ff587827
Create Date: 2026-08-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'c1a2f3b4d5e6'
down_revision: Union[str, Sequence[str], None] = 'a084ff587827'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('remittance', sa.Column('ip_address', sqlmodel.sql.sqltypes.AutoString(length=45), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('remittance', 'ip_address')
