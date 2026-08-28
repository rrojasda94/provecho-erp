"""tanda del kds y borrador del pdv

Dos cosas del parche del PDV (ADR-074, ADR-075):

1. `venta_item.tanda` — en que envio a cocina salio la linea. 1 es el alta del
   pedido y cada `POST /ventas/{id}/items` posterior suma uno. Es lo que le
   devuelve la cronologia al KDS: hasta ahora un aumento a una mesa entraba
   dentro de la misma pastilla que la primera comanda y no habia forma de ver
   que acababa de llegar.

   `server_default='1'` y sin backfill: todo lo vendido hasta hoy fue una sola
   tanda para efectos de la cola, que es exactamente como se venia mostrando.

2. `pedido_borrador` — el ticket a medio armar de una caja, del lado del
   servidor. Vivia solo en la memoria del navegador, asi que recargar la
   pagina borraba las pestanas de pedido.

Revision ID: a1c47e6b90d2
Revises: bf0ea834a972
Create Date: 2026-08-28

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a1c47e6b90d2'
down_revision: str | None = 'bf0ea834a972'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mismo criterio que el resto del proyecto: JSONB en Postgres, JSON en el
# SQLite de los tests.
JSONB = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def upgrade() -> None:
    op.add_column(
        'venta_item',
        sa.Column(
            'tanda', sa.Integer(), nullable=False, server_default='1'
        ),
    )
    op.create_table(
        'pedido_borrador',
        sa.Column('sucursal_id', sa.Uuid(), nullable=False),
        sa.Column('punto_venta_id', sa.Uuid(), nullable=False),
        sa.Column('usuario_id', sa.Uuid(), nullable=False),
        sa.Column('contenido', JSONB, nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['punto_venta_id'],
            ['punto_venta.id'],
            name=op.f('fk_pedido_borrador_punto_venta_id_punto_venta'),
        ),
        sa.ForeignKeyConstraint(
            ['sucursal_id'],
            ['sucursal.id'],
            name=op.f('fk_pedido_borrador_sucursal_id_sucursal'),
        ),
        sa.ForeignKeyConstraint(
            ['usuario_id'],
            ['usuario.id'],
            name=op.f('fk_pedido_borrador_usuario_id_usuario'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_pedido_borrador')),
    )
    # La consulta que corre en cada arranque del PDV es "los borradores de
    # esta caja": sin el indice es un scan de la tabla entera por cada tablet
    # que abre.
    op.create_index(
        op.f('ix_pedido_borrador_punto_venta_id'),
        'pedido_borrador',
        ['punto_venta_id'],
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_pedido_borrador_punto_venta_id'), table_name='pedido_borrador'
    )
    op.drop_table('pedido_borrador')
    op.drop_column('venta_item', 'tanda')
