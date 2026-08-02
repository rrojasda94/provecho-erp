"""postulante.anonimizado_at: cancelacion ARCO de la ficha de candidato

Revision ID: b1d09e574c23
Revises: e9c3b7412a68
Create Date: 2026-08-01 21:40:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b1d09e574c23'
down_revision: str | None = 'e9c3b7412a68'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'postulante',
        sa.Column('anonimizado_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('postulante', 'anonimizado_at')
