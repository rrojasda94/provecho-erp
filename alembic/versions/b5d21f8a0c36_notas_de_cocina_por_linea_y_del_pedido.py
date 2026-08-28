"""notas de cocina por linea y del pedido

Dos columnas para lo que el PDV ya capturaba y tiraba (ADR-075 §notas):

1. `venta_item.nota` - lo que el mesero le dice a cocina sobre ESE plato
   ("bien cocida", "sin sal"). El campo existia en la pantalla desde el
   primer PDV, con sus chips y todo, y el dato nunca viajaba al servidor: no
   habia columna, `cuerpoLinea` no lo mandaba, y al releer la orden se
   perdia. Era decorativo.

2. `venta.nota_cocina` - como se sirve el pedido entero: "servir todo
   junto", "bebidas al final", "primero el pan al ajo". Es del pedido y no
   de una linea: colgarla de la primera la esconderia dentro de un plato, y
   repetirla en todas seria pedirle al cocinero que las compare. El KDS la
   pinta al pie de la pastilla y la comanda la imprime bajo "AL SERVIR:".

Las dos nullable y sin backfill: lo vendido hasta hoy no tenia nota que
guardar.

Revision ID: b5d21f8a0c36
Revises: a1c47e6b90d2
Create Date: 2026-08-28

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b5d21f8a0c36'
down_revision: str | None = 'a1c47e6b90d2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'venta_item', sa.Column('nota', sa.String(length=140), nullable=True)
    )
    op.add_column(
        'venta', sa.Column('nota_cocina', sa.String(length=200), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('venta', 'nota_cocina')
    op.drop_column('venta_item', 'nota')
