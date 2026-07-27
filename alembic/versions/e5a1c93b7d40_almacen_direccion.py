"""almacen direccion

El almacen central no cuelga de ninguna sucursal (sucursal_id NULL), asi que
no habia donde registrar su ubicacion fisica. Nullable: los almacenes
virtuales (`activos`, futuro `transporte`) no tienen direccion, y los de
sucursal heredan la de su sucursal.

Revision ID: e5a1c93b7d40
Revises: e5c47b90f118
Create Date: 2026-07-27

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e5a1c93b7d40'
down_revision: str | None = 'e5c47b90f118'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'almacen',
        sa.Column('direccion', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('almacen', 'direccion')
