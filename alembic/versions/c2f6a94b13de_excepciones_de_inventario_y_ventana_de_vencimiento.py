"""excepciones de inventario, ventana de vencimiento y motivo del override

Revision ID: c2f6a94b13de
Revises: a4c8f21e6b09
Create Date: 2026-08-06 10:20:00.000000

Tres cambios que cierran deuda declarada del módulo inventory:

- `incidencia_inventario`: el movimiento que el listener decide NO hacer
  (sucursal sin almacén, artículo sin SKU, stock teórico insuficiente).
  Hasta ahora esa omisión solo salía por `log.warning` y el stock se iba de
  la realidad sin que quedara dónde verlo.
- `articulo.dias_alerta_vencimiento`: con cuánta anticipación avisa cada
  artículo. Un número global deja a la leche avisando tarde o a la conserva
  avisando siempre.
- `movimiento_inventario.motivo_lote`: por qué se tomó un lote distinto del
  que sugería FEFO. Sin el motivo la traza dice qué salió, no por qué.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c2f6a94b13de'
down_revision: str | None = 'a4c8f21e6b09'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'incidencia_inventario',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column(
            'origen',
            sa.Enum(
                'venta',
                'orden_compra',
                'orden_produccion',
                name='origen_incidencia_inventario',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('referencia', sa.String(length=64), nullable=False),
        sa.Column(
            'tipo',
            sa.Enum(
                'sin_almacen',
                'sin_sku',
                'stock_insuficiente',
                name='tipo_incidencia_inventario',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('almacen_id', sa.Uuid(), nullable=True),
        sa.Column('articulo_id', sa.Uuid(), nullable=True),
        sa.Column('sku_id', sa.Uuid(), nullable=True),
        sa.Column('cantidad', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('detalle', sa.String(length=300), nullable=True),
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
        sa.ForeignKeyConstraint(['almacen_id'], ['almacen.id']),
        sa.ForeignKeyConstraint(['articulo_id'], ['articulo.id']),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id']),
        sa.ForeignKeyConstraint(['sku_id'], ['sku.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_incidencia_inventario_empresa_id'),
        'incidencia_inventario',
        ['empresa_id'],
    )
    op.create_index(
        op.f('ix_incidencia_inventario_referencia'),
        'incidencia_inventario',
        ['referencia'],
    )
    op.add_column(
        'articulo',
        sa.Column('dias_alerta_vencimiento', sa.Integer(), nullable=True),
    )
    op.add_column(
        'movimiento_inventario',
        sa.Column('motivo_lote', sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('movimiento_inventario', 'motivo_lote')
    op.drop_column('articulo', 'dias_alerta_vencimiento')
    op.drop_index(
        op.f('ix_incidencia_inventario_referencia'), table_name='incidencia_inventario'
    )
    op.drop_index(
        op.f('ix_incidencia_inventario_empresa_id'), table_name='incidencia_inventario'
    )
    op.drop_table('incidencia_inventario')
