"""orden_produccion: lote, trazabilidad de fabricación e idempotencia

`fecha_vencimiento`/`lote_codigo` son lo que el listener de `inventory`
(`_lote_del_ingreso`) ya sabía leer del payload de `production.orden_
completada` desde ADR-015 — production nunca los mandaba, así que el lote
del producto terminado nacía siempre sin vencimiento y FEFO lo trataba
como FIFO (RN-VNC-001). `trazabilidad` es la trazabilidad fina de
fabricación que pide RN-LOT-002/003 (manipulador, envasador, línea,
variables de proceso) — sin esquema fijo todavía, JSONB libre.

`consumo_idempotency_key`/`cierre_idempotency_key` (nullable, únicas):
antes solo `crear_orden_produccion` era idempotente; un reintento de red
sobre `/consumo` o `/completar` podía duplicar el consumo o cerrar la
orden dos veces (deuda técnica, ver docs/roadmap/deuda/modulo-production.md).

Revision ID: 48335395076a
Revises: c4f3e14f5bce
Create Date: 2026-09-09 02:54:19.748636

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "48335395076a"
down_revision: str | None = "c4f3e14f5bce"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orden_produccion", sa.Column("fecha_vencimiento", sa.Date(), nullable=True))
    op.add_column(
        "orden_produccion", sa.Column("lote_codigo", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "orden_produccion",
        sa.Column(
            "trazabilidad",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
    )
    op.add_column(
        "orden_produccion",
        sa.Column("consumo_idempotency_key", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "orden_produccion",
        sa.Column("cierre_idempotency_key", sa.String(length=100), nullable=True),
    )
    op.create_unique_constraint(
        op.f("uq_orden_produccion_consumo_idempotency_key"),
        "orden_produccion",
        ["consumo_idempotency_key"],
    )
    op.create_unique_constraint(
        op.f("uq_orden_produccion_cierre_idempotency_key"),
        "orden_produccion",
        ["cierre_idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("uq_orden_produccion_cierre_idempotency_key"),
        "orden_produccion",
        type_="unique",
    )
    op.drop_constraint(
        op.f("uq_orden_produccion_consumo_idempotency_key"),
        "orden_produccion",
        type_="unique",
    )
    op.drop_column("orden_produccion", "cierre_idempotency_key")
    op.drop_column("orden_produccion", "consumo_idempotency_key")
    op.drop_column("orden_produccion", "trazabilidad")
    op.drop_column("orden_produccion", "lote_codigo")
    op.drop_column("orden_produccion", "fecha_vencimiento")
