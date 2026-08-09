"""restas ("sin X") en la línea de venta

`venta_item.sin_articulo_ids`: qué insumos de la receta NO lleva el plato.
Cierra el último tramo de RN-PRD-004 (tamaño → combinación → extras →
restas), el único que nunca se implementó.

Array de `articulo.id` (texto) y no `receta_item.id`: la línea de receta se
edita y se borra, el artículo no. Guardando la línea, una receta corregida
mañana dejaría restas históricas apuntando a nada.

Nullable sin default: NULL = la línea no quitó nada, que es lo que vale para
todo lo ya vendido. Nada cambia de comportamiento con la migración aplicada.

Revision ID: a4f1d0c8b573
Revises: d5c81a7f3b62
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a4f1d0c8b573"
down_revision = "d5c81a7f3b62"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "venta_item",
        sa.Column(
            "sin_articulo_ids",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("venta_item", "sin_articulo_ids")
