"""persona anonimizado_at (Ley 29733 derecho de cancelacion)

Derecho de cancelacion vía anonimizacion, no DELETE: persona la referencian
trabajador/cliente/usuario y un borrado fisico rompería esas FK o dejaría
planillas/comprobantes sin sustento (ver ADR-011).

Revision ID: dad43729501d
Revises: b3d7f21ac094
Create Date: 2026-07-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'dad43729501d'
down_revision: str | None = 'b3d7f21ac094'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'persona',
        sa.Column('anonimizado_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('persona', 'anonimizado_at')
