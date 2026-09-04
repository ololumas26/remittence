"""client_id nullable on remittance (SET NULL on client delete)

Revision ID: d4a5b6c7e8f9
Revises: e7f8a9b0c1d2
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'd4a5b6c7e8f9'
down_revision: Union[str, Sequence[str], None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# A foreign key de client_id foi criada sem nome explícito (op.create_table
# em f39623e69dfc), por isso fica anónima no SQLite. Este naming_convention
# dá-lhe um nome determinístico (mesmo padrão usado para
# fk_remittance_recipient_id_recipient) só para o batch mode conseguir
# referenciá-la no drop_constraint abaixo — não afeta o Postgres, onde a
# introspecção de nome de constraint já funciona de outra forma.
NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def upgrade() -> None:
    """Upgrade schema."""
    # Apagar a conta de um cliente (ver "apagar conta") nunca deve
    # apagar/bloquear o histórico de remessas já feitas — client_id passa a
    # nullable e ganha ondelete='SET NULL', tal como já acontece com
    # recipient_id desde e7f8a9b0c1d2. Em batch mode porque o SQLite não
    # suporta alterar uma foreign key existente sem recriar a tabela.
    with op.batch_alter_table('remittance', schema=None, naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.alter_column('client_id', existing_type=sa.Uuid(), nullable=True)
        batch_op.drop_constraint('fk_remittance_client_id_client', type_='foreignkey')
        batch_op.create_foreign_key(
            'fk_remittance_client_id_client',
            'client',
            ['client_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('remittance', schema=None, naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint('fk_remittance_client_id_client', type_='foreignkey')
        batch_op.create_foreign_key(
            'fk_remittance_client_id_client',
            'client',
            ['client_id'],
            ['id'],
        )
        batch_op.alter_column('client_id', existing_type=sa.Uuid(), nullable=False)
