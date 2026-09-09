"""orden_produccion: origen y creado_por nullable

`origen` distingue quién pidió la orden: `manual` (vía API, como hasta
ahora — semilla de las filas existentes), `ajuste_por_necesidad` (la crea
sola `production.application.listeners.on_stock_bajo_minimo` al cruzar
`inventory.stock_bajo_minimo`, RN-PRD-007/011) o `plan` (cronograma,
diferido). `creado_por` pasa a nullable porque una orden `ajuste_por_
necesidad` no tiene ningún humano detrás — mismo criterio que `usuario_id`
nulo en `inventory.stock_bajo_minimo`, que el reporte muestra como
«Sistema».

`server_default='manual'` solo para que las filas existentes no violen el
NOT NULL al agregar la columna (mismo patrón que `b2e6a1d9f047`, `orden_
compra.origen`); se retira después porque el valor por defecto lo pone el
ORM (`OrdenProduccion.origen`), no la base.

Revision ID: 689b1b94855d
Revises: 35d6767725bd
Create Date: 2026-09-09 16:46:23.650895

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "689b1b94855d"
down_revision: str | None = "35d6767725bd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orden_produccion",
        sa.Column(
            "origen",
            sa.Enum(
                "manual", "ajuste_por_necesidad", "plan",
                name="origen_orden_produccion", native_enum=False,
            ),
            nullable=False,
            server_default="manual",
        ),
    )
    op.alter_column("orden_produccion", "origen", server_default=None)
    op.create_check_constraint(
        "origen_orden_produccion",
        "orden_produccion",
        sa.text("origen IN ('manual', 'ajuste_por_necesidad', 'plan')"),
    )
    op.alter_column(
        "orden_produccion", "creado_por", existing_type=sa.Uuid(), nullable=True
    )


def downgrade() -> None:
    # Falla si ya existe alguna orden `ajuste_por_necesidad` con
    # `creado_por` NULL: no hay humano que inventarle sin mentir la
    # auditoría, así que se prefiere que el downgrade truene a que la
    # invente.
    op.alter_column(
        "orden_produccion", "creado_por", existing_type=sa.Uuid(), nullable=False
    )
    op.drop_constraint("origen_orden_produccion", "orden_produccion", type_="check")
    op.drop_column("orden_produccion", "origen")
