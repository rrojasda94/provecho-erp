"""borra el lienzo_pos del producto comercial

El lienzo se da de baja (ADR-063): los atributos y las variantes se
administran en tablas, no en un canvas. `producto_comercial.lienzo_pos`
—dónde quedaba el nodo, `{"x": .., "y": ..}"`— nació para eso en
`e2b7c40d91af` (ADR-058) y no lo lee nada más.

Rompe la promesa de ADR-055 §6 de que la imagen anterior corre contra este
esquema sin enterarse: volver a una versión que todavía dibuja el lienzo
exige el `downgrade`, que reagrega la columna nullable y pierde las
posiciones guardadas — aceptable, porque son puramente cosméticas.

Revision ID: ce32c6610eb7
Revises: b6d29f10c47e
Create Date: 2026-08-24 17:09:09.104862

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'ce32c6610eb7'
down_revision: str | None = 'b6d29f10c47e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
)


def upgrade() -> None:
    op.drop_column("producto_comercial", "lienzo_pos")


def downgrade() -> None:
    op.add_column(
        "producto_comercial", sa.Column("lienzo_pos", JSONB, nullable=True)
    )
