"""storefront_pedido: estado del pago e id de la pasarela

Con Izipay el pedido ya no se convierte en venta al confirmarse: espera a que
la pasarela avise (webhook) que el pago se aprobó. `pago_estado` guarda esa
espera (`pendiente` | `aprobado` | `rechazado`; NULL en efectivo) y
`pago_id_externo` el identificador del intento en la pasarela, único: es lo que
hace idempotente el webhook (la pasarela reintenta hasta que se le responde).

Ambas columnas NULL-ables, sin backfill: los pedidos existentes (efectivo o
pagados con la pasarela de mentira, que aprobaba en el acto) quedan sin pago
pendiente.

Revision ID: 8131c2cb30d2
Revises: e0abbeea6a86
Create Date: 2026-09-19 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str = "8131c2cb30d2"
down_revision: str | None = "e0abbeea6a86"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "storefront_pedido", sa.Column("pago_estado", sa.String(length=10), nullable=True)
    )
    op.add_column(
        "storefront_pedido",
        sa.Column("pago_id_externo", sa.String(length=100), nullable=True),
    )
    op.create_unique_constraint(
        "uq_storefront_pedido_pago_id_externo", "storefront_pedido", ["pago_id_externo"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_storefront_pedido_pago_id_externo", "storefront_pedido", type_="unique"
    )
    op.drop_column("storefront_pedido", "pago_id_externo")
    op.drop_column("storefront_pedido", "pago_estado")
