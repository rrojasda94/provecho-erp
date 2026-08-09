"""consumo de personal: venta sin precio y salida de inventario propia

La comida que el negocio le da a su personal se prepara y despacha como
cualquier pedido, pero no es venta: vale cero, no se cobra y no emite
comprobante. Su costo es gasto de alimentación de personal (RN-COM-025).

Solo agrega columnas a `venta`. Los valores nuevos de `venta.estado`
(`cerrada`) y de `movimiento_inventario.tipo` (`consumo_interno`) no tocan el
esquema: esos enums son `native_enum=False` **sin** CHECK (default de
SQLAlchemy 2.0), es decir `VARCHAR` — y ambos valores nuevos entran en el
largo ya declarado. La lista válida la hace cumplir el dominio.

Las ventas existentes quedan `tipo='venta'`, que es lo que siempre fueron.

Revision ID: d5c81a7f3b62
Revises: 9a1c4e7b2d30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d5c81a7f3b62"
down_revision = "9a1c4e7b2d30"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)

TIPO_VENTA = sa.Enum(
    "venta", "consumo_personal", name="tipo_venta", native_enum=False
)
MOTIVO_CONSUMO = sa.Enum(
    "fin_semana",
    "feriado",
    "alta_actividad",
    "capacitacion",
    "otro",
    name="motivo_consumo_personal",
    native_enum=False,
)


def upgrade() -> None:
    op.add_column(
        "venta",
        sa.Column("tipo", TIPO_VENTA, nullable=False, server_default="venta"),
    )
    op.add_column("venta", sa.Column("consumo_motivo", MOTIVO_CONSUMO, nullable=True))
    op.add_column(
        "venta",
        sa.Column(
            "consumo_autorizado_por",
            UUID,
            sa.ForeignKey("usuario.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # Un consumo de personal no tiene forma de existir sin la columna que lo
    # distingue de una venta: se borra, o quedaría como venta de S/ 0.00 en
    # todos los reportes. Sus movimientos de inventario ya ocurrieron y se
    # quedan — el insumo salió de verdad.
    op.execute(
        "DELETE FROM venta_item WHERE venta_id IN "
        "(SELECT id FROM venta WHERE tipo = 'consumo_personal')"
    )
    op.execute("DELETE FROM venta WHERE tipo = 'consumo_personal'")
    op.drop_column("venta", "consumo_autorizado_por")
    op.drop_column("venta", "consumo_motivo")
    op.drop_column("venta", "tipo")
