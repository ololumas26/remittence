"""add payment_id to remittance

Revision ID: a8720e502a7e
Revises: c1acf8e75b4a
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'a8720e502a7e'
down_revision: Union[str, Sequence[str], None] = 'c1acf8e75b4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Ligação da remessa ao pagamento que a financiou. Nullable e com ondelete='SET NULL' pela
    # mesma razão de recipient_id/client_id: o histórico da remessa não deve depender do registo
    # de pagamento continuar a existir. Em batch mode porque o SQLite (dev) não suporta adicionar
    # uma nova foreign key a uma tabela existente sem recriá-la — o Alembic trata disso
    # automaticamente em modo batch, sem alterações em Postgres.
    with op.batch_alter_table('remittance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('payment_id', sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            'fk_remittance_payment_id_payment',
            'payment',
            ['payment_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('remittance', schema=None) as batch_op:
        batch_op.drop_constraint('fk_remittance_payment_id_payment', type_='foreignkey')
        batch_op.drop_column('payment_id')
