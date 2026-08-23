"""la venta guarda su entrega

La direccion de delivery se tecleaba en caja y se perdia: vivia solo en el
borrador del navegador (`frontend/app/pdv/tipos.ts`) y `venta` no tenia
ninguna columna que la recibiera. `referencia_atencion` es "para quien es el
pedido" -50 caracteres, "Carlos", "Rappi #1042"-, no adonde va.

Con la direccion entran su ancla en el mapa y lo que se cobro por llevarla.
Las dos ultimas se congelan al crear la orden (ADR-054): la tarifa por
kilometro cambia y el pedido de ayer no puede cambiar de precio, igual que
la guia de remision congela sus direcciones al emitirse.

Todo nullable: mesa y takeout no tienen adonde ir, y las ventas anteriores a
este cambio tampoco.

Revision ID: d41f6a2c98b7
Revises: c3d8b1f47a95
Create Date: 2026-08-22

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd41f6a2c98b7'
down_revision: str | None = 'c3d8b1f47a95'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNAS = (
    ('direccion_entrega', sa.String(length=255)),
    ('ubicacion_place_id', sa.String(length=255)),
    ('ubicacion_lat', sa.Numeric(9, 6)),
    ('ubicacion_lng', sa.Numeric(9, 6)),
    ('ubicacion_plus_code', sa.String(length=20)),
    ('ubicacion_distrito', sa.String(length=100)),
    # 6,2 alcanza para 9999,99 km: el reparto propio no llega ni a tres
    # cifras, y el limite deja ver un dato absurdo en vez de guardarlo.
    ('distancia_entrega_km', sa.Numeric(6, 2)),
    ('costo_entrega', sa.Numeric(10, 2)),
)


def upgrade() -> None:
    for nombre, tipo in COLUMNAS:
        op.add_column('venta', sa.Column(nombre, tipo, nullable=True))


def downgrade() -> None:
    for nombre, _ in reversed(COLUMNAS):
        op.drop_column('venta', nombre)
