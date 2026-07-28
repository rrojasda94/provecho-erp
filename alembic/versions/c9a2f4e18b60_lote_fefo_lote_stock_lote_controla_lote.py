"""lote/FEFO: lote, stock_lote, articulo.controla_lote, movimiento.lote_id

Revision ID: c9a2f4e18b60
Revises: d4b1f0a7c3e9
Create Date: 2026-07-27 16:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'c9a2f4e18b60'
down_revision: str | None = 'd4b1f0a7c3e9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'lote',
        sa.Column('articulo_id', sa.Uuid(), nullable=False),
        sa.Column('codigo', sa.String(length=50), nullable=False),
        sa.Column('fecha_vencimiento', sa.Date(), nullable=True),
        sa.Column('fecha_elaboracion', sa.Date(), nullable=True),
        sa.Column('origen', sa.Enum('compra', 'produccion', 'carga_inicial', 'ajuste', name='origen_lote', native_enum=False), nullable=False),
        sa.Column('referencia', sa.String(length=100), nullable=True),
        sa.Column('condicion_almacenamiento', sa.Enum('refrigerado', 'congelado', 'ambiente', name='condicion_almacenamiento', native_enum=False), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['articulo_id'], ['articulo.id'], name=op.f('fk_lote_articulo_id_articulo')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_lote')),
        sa.UniqueConstraint('articulo_id', 'codigo', name=op.f('uq_lote_articulo_id')),
    )
    op.create_table(
        'stock_lote',
        sa.Column('almacen_id', sa.Uuid(), nullable=False),
        sa.Column('sku_id', sa.Uuid(), nullable=False),
        sa.Column('lote_id', sa.Uuid(), nullable=False),
        sa.Column('cantidad', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('estado', sa.Enum('disponible', 'bloqueado', 'agotado', name='estado_stock_lote', native_enum=False), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['almacen_id'], ['almacen.id'], name=op.f('fk_stock_lote_almacen_id_almacen')),
        sa.ForeignKeyConstraint(['lote_id'], ['lote.id'], name=op.f('fk_stock_lote_lote_id_lote')),
        sa.ForeignKeyConstraint(['sku_id'], ['sku.id'], name=op.f('fk_stock_lote_sku_id_sku')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_lote')),
        sa.UniqueConstraint('almacen_id', 'sku_id', 'lote_id', name=op.f('uq_stock_lote_almacen_id')),
    )
    # `server_default` solo para poblar las filas existentes: el default real
    # vive en el modelo. Sin él, un ALTER NOT NULL sobre tabla con datos falla.
    op.add_column(
        'articulo',
        sa.Column('controla_lote', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('articulo', 'controla_lote', server_default=None)
    with op.batch_alter_table('movimiento_inventario') as batch:
        batch.add_column(sa.Column('lote_id', sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f('fk_movimiento_inventario_lote_id_lote'), 'lote', ['lote_id'], ['id'],
        )


def downgrade() -> None:
    with op.batch_alter_table('movimiento_inventario') as batch:
        batch.drop_constraint(op.f('fk_movimiento_inventario_lote_id_lote'), type_='foreignkey')
        batch.drop_column('lote_id')
    op.drop_column('articulo', 'controla_lote')
    op.drop_table('stock_lote')
    op.drop_table('lote')
