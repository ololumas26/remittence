"""add note to document and document_id to notification

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('document', sa.Column('note', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True))

    # Em batch mode pela mesma razão de a8720e502a7e (add_payment_id_to_remittance): o SQLite
    # (dev) não suporta adicionar uma nova foreign key/constraint a uma tabela existente sem a
    # recriar — o Alembic trata disso automaticamente em modo batch, sem alterações em Postgres.
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.add_column(sa.Column('document_id', sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            'fk_notification_document_id_document',
            'document',
            ['document_id'],
            ['id'],
            ondelete='SET NULL',
        )
        # remittance_id e document_id nunca estão os dois preenchidos na mesma notificação, e
        # NULL nunca colide consigo mesmo numa UNIQUE constraint — esta constraint só "está
        # ativa" para notificações de documento, não interfere com uq_notification_remittance_type.
        batch_op.create_unique_constraint(
            'uq_notification_document_type',
            ['document_id', 'type'],
        )
        batch_op.create_index('ix_notification_document_id', ['document_id'])

    # DOCUMENT_APPROVED/DOCUMENT_REJECTED são novos no NotificationType — em Postgres o tipo
    # nativo "notificationtype" (criado em b35c91d2e4f6) tem de ganhar os novos valores
    # explicitamente. Nomes em maiúsculas porque sa.Enum usa o NAME do membro Python (não o
    # .value), tal como os valores já existentes (REMITTANCE_CREATED, etc). No SQLite a coluna
    # "type" é só VARCHAR sem CHECK constraint (ver notification na base local) — não precisa de
    # nenhum passo aqui.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'DOCUMENT_APPROVED'")
        op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'DOCUMENT_REJECTED'")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.drop_index('ix_notification_document_id')
        batch_op.drop_constraint('uq_notification_document_type', type_='unique')
        batch_op.drop_constraint('fk_notification_document_id_document', type_='foreignkey')
        batch_op.drop_column('document_id')

    op.drop_column('document', 'note')
    # Nota: reverter valores adicionados a um ENUM do Postgres não é suportado de forma segura
    # (exigiria recriar o tipo e todas as colunas que o usam) — os dois valores novos ficam no
    # tipo mesmo depois do downgrade, tal como já seria o caso em qualquer migração deste tipo.
