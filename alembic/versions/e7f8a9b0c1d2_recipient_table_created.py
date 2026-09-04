"""recipient table created

Revision ID: e7f8a9b0c1d2
Revises: c1a2f3b4d5e6
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = 'c1a2f3b4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('recipient',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('client_id', sa.Uuid(), nullable=False),
    sa.Column('full_name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.Column('account_iban', sqlmodel.sql.sqltypes.AutoString(length=35), nullable=False),
    sa.Column('location', sqlmodel.sql.sqltypes.AutoString(length=120), nullable=True),
    sa.Column('relationship', sqlmodel.sql.sqltypes.AutoString(length=60), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['client_id'], ['client.id'], ),
    sa.PrimaryKeyConstraint('id'),
    )

    # Ligação da remessa ao destinatário que a originou. Em batch mode
    # porque o SQLite (usado em dev) não suporta adicionar uma nova foreign
    # key a uma tabela existente sem recriá-la — o Alembic trata disso
    # automaticamente em modo batch, e continua a funcionar sem alterações
    # em Postgres.
    with op.batch_alter_table('remittance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('recipient_id', sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            'fk_remittance_recipient_id_recipient',
            'recipient',
            ['recipient_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('remittance', schema=None) as batch_op:
        batch_op.drop_constraint('fk_remittance_recipient_id_recipient', type_='foreignkey')
        batch_op.drop_column('recipient_id')

    op.drop_table('recipient')
