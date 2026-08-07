"""devolución, lote de la merma y guía de devolución

Revision ID: e7c390a5b41f
Revises: d5b81e0c37a4
Create Date: 2026-08-06 18:05:00.000000

Cierra el bloque de deuda "slices grandes" del módulo inventory:

- **`devolucion` + `devolucion_item`**: lo que se le devuelve al proveedor
  (sale del almacén, con su guía) y lo que devuelve un cliente (entra, y
  `destino` decide si vuelve al estante o se aparta como merma). La
  devolución sucursal→central no está acá a propósito: es una
  transferencia (ADR-020), que ya tiene despacho, tránsito y recepción.
- **`reserva_stock.lote_id`**: la merma **es** un lote concreto —lo vencido
  o dañado no es "algo de ese SKU"— y el desecho tiene que sacar ese y no
  el que FEFO elegiría. No hay tabla `stock_merma`: la merma es una reserva
  de tipo `merma`, ver ADR-028.
- **`guia_remision.transferencia_id` pasa a nullable** y aparece
  `devolucion_id`: una devolución a proveedor también viaja por la vía
  pública y SUNAT no distingue el motivo. La migración es aditiva; el
  camino contrario no lo sería, y por eso la columna arrancó estricta.
- **`recepcion_item.lote_codigo` / `fecha_vencimiento`**: lo que declaró el
  proveedor queda en el documento de recepción, no solo en el evento que
  viaja a `inventory`. Si el listener falla, antes se perdía.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e7c390a5b41f'
down_revision: str | None = 'd5b81e0c37a4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'devolucion',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('almacen_id', sa.Uuid(), nullable=False),
        sa.Column(
            'origen',
            sa.Enum('proveedor', 'cliente', name='origen_devolucion',
                    native_enum=False),
            nullable=False,
        ),
        sa.Column('referencia_id', sa.Uuid(), nullable=True),
        sa.Column(
            'motivo',
            sa.Enum('vencido', 'dañado', 'incumplimiento_plazo', 'no_requerido',
                    'error_solicitud', 'duplicidad', name='motivo_devolucion',
                    native_enum=False),
            nullable=False,
        ),
        sa.Column(
            'destino',
            sa.Enum('desecho', 'auditoria', 'reintegro',
                    name='destino_devolucion', native_enum=False),
            nullable=True,
        ),
        sa.Column(
            'estado',
            sa.Enum('registrada', 'anulada', name='estado_devolucion',
                    native_enum=False),
            nullable=False,
        ),
        sa.Column('reporte_dirigido_a', sa.String(length=20), nullable=False),
        sa.Column('observacion', sa.String(length=500), nullable=True),
        sa.Column('registrado_por', sa.Uuid(), nullable=False),
        sa.Column('anulado_por', sa.Uuid(), nullable=True),
        sa.Column('anulada_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.ForeignKeyConstraint(['almacen_id'], ['almacen.id']),
        sa.ForeignKeyConstraint(['anulado_por'], ['usuario.id']),
        sa.ForeignKeyConstraint(['registrado_por'], ['usuario.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'devolucion_item',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('devolucion_id', sa.Uuid(), nullable=False),
        sa.Column('sku_id', sa.Uuid(), nullable=False),
        sa.Column('cantidad', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('lote_id', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['devolucion_id'], ['devolucion.id']),
        sa.ForeignKeyConstraint(['lote_id'], ['lote.id']),
        sa.ForeignKeyConstraint(['sku_id'], ['sku.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.add_column('reserva_stock', sa.Column('lote_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_reserva_stock_lote_id_lote', 'reserva_stock', 'lote', ['lote_id'], ['id']
    )

    op.add_column(
        'guia_remision', sa.Column('devolucion_id', sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        'fk_guia_remision_devolucion_id_devolucion',
        'guia_remision', 'devolucion', ['devolucion_id'], ['id'],
    )
    op.create_unique_constraint(
        'uq_guia_remision_devolucion_id', 'guia_remision', ['devolucion_id']
    )
    op.alter_column('guia_remision', 'transferencia_id', nullable=True)

    op.add_column(
        'recepcion_item', sa.Column('lote_codigo', sa.String(length=50), nullable=True)
    )
    op.add_column(
        'recepcion_item', sa.Column('fecha_vencimiento', sa.Date(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('recepcion_item', 'fecha_vencimiento')
    op.drop_column('recepcion_item', 'lote_codigo')

    # Una guía sin transferencia no cabe en el esquema anterior; son las de
    # devolución, que antes no podían existir.
    op.execute("DELETE FROM guia_remision_item WHERE guia_remision_id IN "
               "(SELECT id FROM guia_remision WHERE transferencia_id IS NULL)")
    op.execute("DELETE FROM guia_remision WHERE transferencia_id IS NULL")
    op.alter_column('guia_remision', 'transferencia_id', nullable=False)
    op.drop_constraint(
        'uq_guia_remision_devolucion_id', 'guia_remision', type_='unique'
    )
    op.drop_constraint(
        'fk_guia_remision_devolucion_id_devolucion', 'guia_remision',
        type_='foreignkey',
    )
    op.drop_column('guia_remision', 'devolucion_id')

    op.drop_constraint(
        'fk_reserva_stock_lote_id_lote', 'reserva_stock', type_='foreignkey'
    )
    op.drop_column('reserva_stock', 'lote_id')

    op.drop_table('devolucion_item')
    op.drop_table('devolucion')
