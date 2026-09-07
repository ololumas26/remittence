"""add image_url to client

Revision ID: 24b268831668
Revises: a8720e502a7e
Create Date: 2026-09-07 11:42:07.783450

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '24b268831668'
down_revision: Union[str, Sequence[str], None] = 'a8720e502a7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # URL pública da foto de perfil no Supabase Storage. Nullable — sem foto, o frontend mostra
    # as iniciais do nome (ver Client.image_url). Batch mode pela mesma razão de sempre: o SQLite
    # (dev) não suporta ALTER TABLE ADD COLUMN diretamente numa tabela com constraints, o Alembic
    # trata disso automaticamente sem alterações em Postgres.
    with op.batch_alter_table('client', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_url', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('client', schema=None) as batch_op:
        batch_op.drop_column('image_url')
