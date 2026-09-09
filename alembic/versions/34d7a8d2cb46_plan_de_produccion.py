"""plan de producción

Nueva tabla `plan_produccion`: el cronograma fijo por línea/turno que la
orden ad-hoc de siempre no tenía (RN-PRD-007/012, bloque `feat/produccion-
plan-de-produccion`). `turno`/`linea_produccion` son texto libre, no un
catálogo con FK — `turno_sucursal` (RRHH) está atado a una sucursal y una
cocina de producción central no siempre tiene una. La exclusividad real
la da el `UniqueConstraint(almacen_id, fecha, turno, linea_produccion)`.

`orden_produccion.plan_produccion_id` (nullable) liga la orden a su plan
cuando `application/planes.py::agregar_orden` la crea desde uno; la
mayoría de las órdenes de hoy siguen sin plan.

Revision ID: 34d7a8d2cb46
Revises: 689b1b94855d
Create Date: 2026-09-09 17:15:11.371693

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "34d7a8d2cb46"
down_revision: str | None = "689b1b94855d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plan_produccion",
        sa.Column("almacen_id", sa.Uuid(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("turno", sa.String(length=30), nullable=False),
        sa.Column("linea_produccion", sa.String(length=100), nullable=False),
        sa.Column(
            "origen",
            sa.Enum(
                "cronograma_fijo", "ajuste_por_necesidad",
                name="origen_plan_produccion", native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "estado",
            sa.Enum(
                "planificado", "en_ejecucion", "cerrado",
                name="estado_plan_produccion", native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "estado IN ('planificado', 'en_ejecucion', 'cerrado')",
            name=op.f("ck_plan_produccion_estado_plan_produccion"),
        ),
        sa.CheckConstraint(
            "origen IN ('cronograma_fijo', 'ajuste_por_necesidad')",
            name=op.f("ck_plan_produccion_origen_plan_produccion"),
        ),
        sa.ForeignKeyConstraint(
            ["almacen_id"], ["almacen.id"], name=op.f("fk_plan_produccion_almacen_id_almacen")
        ),
        sa.ForeignKeyConstraint(
            ["creado_por"], ["usuario.id"], name=op.f("fk_plan_produccion_creado_por_usuario")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_produccion")),
        sa.UniqueConstraint(
            "almacen_id", "fecha", "turno", "linea_produccion",
            name=op.f("uq_plan_produccion_almacen_id"),
        ),
    )
    op.add_column(
        "orden_produccion", sa.Column("plan_produccion_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_orden_produccion_plan_produccion_id_plan_produccion"),
        "orden_produccion", "plan_produccion", ["plan_produccion_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_orden_produccion_plan_produccion_id_plan_produccion"),
        "orden_produccion", type_="foreignkey",
    )
    op.drop_column("orden_produccion", "plan_produccion_id")
    op.drop_table("plan_produccion")
