"""movimiento de efectivo en caja durante el turno

El turno real no es solo vender: se le paga al repartidor, se compra hielo,
entra el vuelto que faltaba. Sin registrar esos movimientos el cierre cuadra
contra un esperado irreal y el descuadre se le atribuye al cajero
(RN-MDP-006).

Distinto de `movimiento_dinero`, que es tesorería (pagos a proveedor desde
banco). Esto es exclusivamente el efectivo físico de UNA apertura de caja.

Tabla nueva: los cierres ya registrados no cambian, su neto de movimientos
es cero.

Revision ID: a3f0d29b6c81
Revises: f2a8c15e94d7
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a3f0d29b6c81"
down_revision = "f2a8c15e94d7"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "movimiento_caja",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "apertura_caja_id",
            UUID,
            sa.ForeignKey("apertura_caja.id"),
            nullable=False,
        ),
        sa.Column(
            "tipo",
            sa.Enum(
                "ingreso", "retiro", name="tipo_movimiento_caja", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("monto", sa.Numeric(10, 2), nullable=False),
        sa.Column("motivo", sa.String(length=120), nullable=False),
        sa.Column(
            "registrado_por", UUID, sa.ForeignKey("usuario.id"), nullable=False
        ),
        sa.Column(
            "autorizado_por", UUID, sa.ForeignKey("usuario.id"), nullable=True
        ),
        sa.Column(
            "idempotency_key", sa.String(length=100), nullable=False, unique=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_movimiento_caja_apertura_caja_id", "movimiento_caja", ["apertura_caja_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_movimiento_caja_apertura_caja_id", table_name="movimiento_caja")
    op.drop_table("movimiento_caja")
