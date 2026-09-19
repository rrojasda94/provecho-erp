"""storefront_pedido_item: extras y sabores elegidos

La línea de un pedido web deja de ser "producto + cantidad": puede llevar extras
(cada uno con su cantidad y precio congelado) y valores de atributo (los sabores
de una Mitad x Mitad, con el recargo que sumaron). Se guardan como JSON en la
propia fila —son una foto para mostrar en `/pedido/{id}`; lo autoritativo lo
vuelve a fijar `sales` al crear la venta—.

Ambas columnas NULL-ables, sin backfill: las líneas existentes no llevaban nada.

Revision ID: 5c1a7e90d4b3
Revises: 8131c2cb30d2
Create Date: 2026-09-19 00:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "5c1a7e90d4b3"
down_revision: str | None = "8131c2cb30d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "storefront_pedido_item",
        sa.Column("extras", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "storefront_pedido_item",
        sa.Column("valores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("storefront_pedido_item", "valores")
    op.drop_column("storefront_pedido_item", "extras")
