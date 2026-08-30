"""ajuste.lote_id: lote declarado al solicitar una entrada manual

Revision ID: f74025d6c871
Revises: 0a056863874b
Create Date: 2026-08-30 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'f74025d6c871'
down_revision: str | None = '0a056863874b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('ajuste') as batch:
        batch.add_column(sa.Column('lote_id', sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f('fk_ajuste_lote_id_lote'), 'lote', ['lote_id'], ['id'],
        )


def downgrade() -> None:
    with op.batch_alter_table('ajuste') as batch:
        batch.drop_constraint(op.f('fk_ajuste_lote_id_lote'), type_='foreignkey')
        batch.drop_column('lote_id')
