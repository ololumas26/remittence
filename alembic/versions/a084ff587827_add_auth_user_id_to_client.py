"""add auth_user_id to client

Revision ID: a084ff587827
Revises: f39623e69dfc
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'a084ff587827'
down_revision: Union[str, Sequence[str], None] = 'f39623e69dfc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('client', sa.Column('auth_user_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_client_auth_user_id'), 'client', ['auth_user_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_client_auth_user_id'), table_name='client')
    op.drop_column('client', 'auth_user_id')
