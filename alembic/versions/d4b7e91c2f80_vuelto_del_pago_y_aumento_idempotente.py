"""vuelto del pago y aumento idempotente

Dos columnas del parche 0.8.1.

`pago.vuelto` (ADR-077): el efectivo ya puede recibir mas de lo que se debe.
`monto` sigue siendo lo que se aplica a la cuenta —lo que contabilidad
asienta— y `vuelto` lo que salio del cajon. Antes el vuelto se calculaba en
el navegador y moria ahi, asi que el arqueo no tenia forma de explicar por
que el cajon tenia menos billetes que la suma de los cobros.

`venta_item.idempotency_key` (RN-COM-002, ADR-075): el alta de la venta ya
era idempotente pero el aumento no. Un reintento sobre una respuesta perdida
mandaba el mismo envio dos veces y la cocina recibia dos comandas identicas
que nadie podia distinguir de un pedido real de dos rondas. Va en la PRIMERA
fila del lote porque lo idempotente es el envio entero, no la linea; nullable
porque todo lo anterior a esta columna no la tiene.

Sin backfill: los pagos viejos no tuvieron vuelto (`server_default '0'`) y
los aumentos viejos ya ocurrieron.

Revision ID: d4b7e91c2f80
Revises: c8e4f30b7a19
Create Date: 2026-08-28

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd4b7e91c2f80'
down_revision: str | None = 'c8e4f30b7a19'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'pago',
        sa.Column(
            'vuelto',
            sa.Numeric(precision=10, scale=2),
            server_default='0',
            nullable=False,
        ),
    )
    op.add_column(
        'venta_item',
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
    )
    op.create_unique_constraint(
        'uq_venta_item_idempotency_key', 'venta_item', ['idempotency_key']
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_venta_item_idempotency_key', 'venta_item', type_='unique'
    )
    op.drop_column('venta_item', 'idempotency_key')
    op.drop_column('pago', 'vuelto')
