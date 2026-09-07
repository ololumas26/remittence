"""payment table created

Revision ID: c1acf8e75b4a
Revises: d4a5b6c7e8f9
Create Date: 2026-09-05 20:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'c1acf8e75b4a'
down_revision: Union[str, Sequence[str], None] = 'd4a5b6c7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # client_id nasce já nullable com ondelete='SET NULL' e com o nome de constraint explícito
    # (mesmo padrão de fk_remittance_recipient_id_recipient) — ao contrário de
    # fk_remittance_client_id_client, que nasceu anónimo e só ganhou isto depois em
    # d4a5b6c7e8f9, exigindo o hack do NAMING_CONVENTION para conseguir referenciá-lo em batch
    # mode. Aqui evitamos esse retrabalho por ser uma tabela nova.
    op.create_table('payment',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('client_id', sa.Uuid(), nullable=True),
    sa.Column('method', sa.Enum('MBWAY', 'CARD', 'MULTIBANK', name='paymentmethod'), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'SUCCEEDED', 'FAILED', name='paymentstatus'), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('provider_reference', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
    sa.Column('failure_reason', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['client_id'], ['client.id'], name='fk_payment_client_id_client', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('payment')
