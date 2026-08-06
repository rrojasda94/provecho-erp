"""guia de remision de traslados entre almacenes

Revision ID: a4c8f21e6b09
Revises: c2f7a91b4e08
Create Date: 2026-08-05 11:20:00.000000

Guía de remisión (RN-GDR-001..003, RN-TRP-002), colgando de `transferencia`
porque lo que declara es un traslado y el traslado es un hecho de
inventario.

Dos restricciones de unicidad hacen el trabajo pesado:

- `(empresa_id, serie, correlativo)`: la numeración de SUNAT no admite
  repetidos, y un hueco o un duplicado hay que justificarlos en una
  fiscalización.
- `transferencia_id` único: un traslado, una guía. Dos guías del mismo
  traslado declararían la misma mercadería dos veces.

`guia_remision_item` agrupa por SKU y no por lote: el reparto FEFO es
control interno y sigue entero en `transferencia_item`.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a4c8f21e6b09'
down_revision: str | None = 'c2f7a91b4e08'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'guia_remision',
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column('transferencia_id', sa.Uuid(), nullable=False),
        sa.Column('serie', sa.String(length=10), nullable=False),
        sa.Column('correlativo', sa.Integer(), nullable=False),
        sa.Column('fecha_inicio_traslado', sa.Date(), nullable=False),
        sa.Column(
            'motivo_traslado',
            sa.Enum(
                '01', '04', '13', '18',
                name='motivo_traslado_guia',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            'modalidad_traslado',
            sa.Enum(
                '01', '02',
                name='modalidad_traslado_guia',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('peso_bruto_kg', sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column('ruc_emisor', sa.String(length=11), nullable=False),
        sa.Column('ruc_receptor', sa.String(length=11), nullable=False),
        sa.Column('lugar_origen', sa.String(length=255), nullable=False),
        sa.Column('lugar_destino', sa.String(length=255), nullable=False),
        sa.Column('chofer_nombres', sa.String(length=120), nullable=False),
        sa.Column('chofer_apellidos', sa.String(length=120), nullable=False),
        sa.Column('chofer_num_doc', sa.String(length=15), nullable=False),
        sa.Column('chofer_licencia', sa.String(length=20), nullable=False),
        sa.Column('vehiculo_placa', sa.String(length=10), nullable=False),
        sa.Column('emitida_por', sa.Uuid(), nullable=False),
        sa.Column('observacion', sa.String(length=500), nullable=True),
        sa.Column(
            'estado_emision',
            sa.Enum(
                'pendiente', 'aceptado', 'rechazado', 'error',
                name='estado_emision_guia',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('hash_proveedor', sa.String(length=120), nullable=True),
        sa.Column('detalle_emision', sa.Text(), nullable=True),
        sa.Column('intentos_emision', sa.Integer(), nullable=False),
        sa.Column(
            'respuesta_proveedor',
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'),
            nullable=True,
        ),
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
            ['empresa_id'],
            ['empresa.id'],
            name=op.f('fk_guia_remision_empresa_id_empresa'),
        ),
        sa.ForeignKeyConstraint(
            ['transferencia_id'],
            ['transferencia.id'],
            name=op.f('fk_guia_remision_transferencia_id_transferencia'),
        ),
        sa.ForeignKeyConstraint(
            ['emitida_por'],
            ['usuario.id'],
            name=op.f('fk_guia_remision_emitida_por_usuario'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_guia_remision')),
        sa.UniqueConstraint(
            'empresa_id', 'serie', 'correlativo',
            name='uq_guia_remision_empresa_id_serie_correlativo',
        ),
        sa.UniqueConstraint(
            'transferencia_id', name='uq_guia_remision_transferencia_id'
        ),
    )
    op.create_table(
        'guia_remision_item',
        sa.Column('guia_remision_id', sa.Uuid(), nullable=False),
        sa.Column('sku_id', sa.Uuid(), nullable=False),
        sa.Column('cantidad', sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column('descripcion', sa.String(length=255), nullable=False),
        sa.Column('unidad', sa.String(length=5), nullable=False),
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
            ['guia_remision_id'],
            ['guia_remision.id'],
            name=op.f('fk_guia_remision_item_guia_remision_id_guia_remision'),
        ),
        sa.ForeignKeyConstraint(
            ['sku_id'], ['sku.id'], name=op.f('fk_guia_remision_item_sku_id_sku')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_guia_remision_item')),
    )


def downgrade() -> None:
    op.drop_table('guia_remision_item')
    op.drop_table('guia_remision')
