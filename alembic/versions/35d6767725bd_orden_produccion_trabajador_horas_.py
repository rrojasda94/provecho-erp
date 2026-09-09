"""orden_produccion_trabajador: horas-hombre desde asistencia de RRHH

`CompletarOrdenIn.horas_hombre` era un número libre que quien completaba
la orden tecleaba, pese a que RRHH ya tiene asistencia real
(`rrhh.application.queries_publicas.horas_asistidas`, bloque
`feat/rrhh-horas-asistidas-contrato-publico`). Ahora se imputan
trabajadores concretos (`trabajador_id` + horas opcionales, tope lo
asistido ese día — RN-RRHH-009) y `orden_produccion.horas_hombre` pasa a
ser el agregado (`Σ horas`) en vez del dato tipeado.

Sin `downgrade` que reconstruya `horas_hombre` desde estas filas: el
agregado ya vivía en la columna de `orden_produccion`, que esta migración
no toca — solo se pierde el detalle por trabajador, no el total.

Revision ID: 35d6767725bd
Revises: c405c74872f3
Create Date: 2026-09-09 16:16:24.555276

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "35d6767725bd"
down_revision: str | None = "c405c74872f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orden_produccion_trabajador",
        sa.Column("orden_produccion_id", sa.Uuid(), nullable=False),
        sa.Column("trabajador_id", sa.Uuid(), nullable=False),
        sa.Column("horas", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["orden_produccion_id"],
            ["orden_produccion.id"],
            name=op.f("fk_orden_produccion_trabajador_orden_produccion_id_orden_produccion"),
        ),
        sa.ForeignKeyConstraint(
            ["trabajador_id"],
            ["trabajador.id"],
            name=op.f("fk_orden_produccion_trabajador_trabajador_id_trabajador"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orden_produccion_trabajador")),
    )


def downgrade() -> None:
    op.drop_table("orden_produccion_trabajador")
