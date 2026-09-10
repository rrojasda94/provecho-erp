"""orden_produccion: costeo real y consumo por otra UdM

`costo_teorico_insumos` es el snapshot de lo que la receta BOM dice que
debería costar la orden, escalada a `cantidad_planeada` (RN-PRD-018) —
se fija al registrar el consumo, para comparar contra `costo_insumos`
(lo que de verdad se consumió) al completar. Antes el costeo "automático"
recibía el `costo_unitario` tipeado por el cliente en vez de leer
`articulo.costo_promedio`, sin ninguna referencia contra la que
contrastarlo.

`consumo_produccion_item.unidad_medida_id` (nullable = la del artículo,
mismo criterio que `receta_item.unidad_medida_id`) deja constancia de en
qué UdM se tecleó la cantidad cuando no fue la del artículo (RN-UDM-005,
ej. gramos sobre un insumo que se lleva en kilos) — la columna `cantidad`
ya viaja convertida a la del artículo, así que esta es solo trazabilidad.

Revision ID: 1dfa85b51a5d
Revises: 48335395076a
Create Date: 2026-09-09 15:18:14.271738

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "1dfa85b51a5d"
down_revision: str | None = "48335395076a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "consumo_produccion_item", sa.Column("unidad_medida_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_consumo_produccion_item_unidad_medida_id_unidad_medida"),
        "consumo_produccion_item",
        "unidad_medida",
        ["unidad_medida_id"],
        ["id"],
    )
    op.add_column(
        "orden_produccion",
        sa.Column("costo_teorico_insumos", sa.Numeric(precision=12, scale=4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orden_produccion", "costo_teorico_insumos")
    op.drop_constraint(
        op.f("fk_consumo_produccion_item_unidad_medida_id_unidad_medida"),
        "consumo_produccion_item",
        type_="foreignkey",
    )
    op.drop_column("consumo_produccion_item", "unidad_medida_id")
