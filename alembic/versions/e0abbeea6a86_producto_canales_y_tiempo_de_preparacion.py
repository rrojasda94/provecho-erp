"""producto_comercial: canales de venta y tiempo de preparación

`canales` deja sacar de un canal lo que solo existe en otro (una caja, una
propina, un ítem del PDV que la web no debe vender). `tiempo_preparacion_min`
alimenta el estimado de espera del sitio: hasta ahora era una base fija más la
cola, igual para una botella de agua que para seis pizzas.

Ambas columnas son NULL-able sin backfill: NULL en `canales` = todos los
canales, NULL en `tiempo_preparacion_min` = "no se sabe" (el sitio usa su base
estándar).

Revision ID: e0abbeea6a86
Revises: 3070159f64bd
Create Date: 2026-09-19 00:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e0abbeea6a86"
down_revision: str | None = "3070159f64bd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "producto_comercial",
        sa.Column("canales", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "producto_comercial",
        sa.Column("tiempo_preparacion_min", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("producto_comercial", "tiempo_preparacion_min")
    op.drop_column("producto_comercial", "canales")
