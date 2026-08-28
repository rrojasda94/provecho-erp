"""promociones condicionales

El motor de promociones que se aplican solas (ADR-076): `promocion` con su
vigencia, su ambito y su condicion/beneficio en JSONB, y `venta_promocion`
con lo que cada pedido activo.

`venta_promocion` es tabla propia y **no** columnas en `venta`: un pedido
puede activar mas de una, y aplanarlas obligaria a elegir cual se guarda.

Ninguna de las dos toca `venta.descuento_*`. Esos campos son el descuento
manual —un acto humano con motivo y autorizador— y mezclarlos haria imposible
que el reporte distinga lo que regalo un supervisor de lo que aplico una
regla, que es el dato por el que existen.

Revision ID: c8e4f30b7a19
Revises: b5d21f8a0c36
Create Date: 2026-08-28

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'c8e4f30b7a19'
down_revision: str | None = 'b5d21f8a0c36'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def upgrade() -> None:
    op.create_table(
        'promocion',
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column('nombre', sa.String(length=120), nullable=False),
        sa.Column('activa', sa.Boolean(), nullable=False),
        sa.Column('desde', sa.Date(), nullable=True),
        sa.Column('hasta', sa.Date(), nullable=True),
        sa.Column('dias_semana', JSONB, nullable=True),
        sa.Column('hora_desde', sa.Time(), nullable=True),
        sa.Column('hora_hasta', sa.Time(), nullable=True),
        sa.Column('marca_id', sa.Uuid(), nullable=True),
        sa.Column('sucursal_id', sa.Uuid(), nullable=True),
        sa.Column('canales', JSONB, nullable=True),
        sa.Column('modalidades', JSONB, nullable=True),
        sa.Column('prioridad', sa.Integer(), server_default='0', nullable=False),
        sa.Column('acumulable', sa.Boolean(), server_default='0', nullable=False),
        sa.Column(
            'tipo',
            sa.Enum(
                'nxm',
                'cantidad',
                'combo',
                'monto_minimo',
                name='tipo_promocion',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('condicion', JSONB, nullable=False),
        sa.Column('beneficio', JSONB, nullable=False),
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
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresa.id'], name=op.f('fk_promocion_empresa_id_empresa')
        ),
        sa.ForeignKeyConstraint(
            ['marca_id'], ['marca.id'], name=op.f('fk_promocion_marca_id_marca')
        ),
        sa.ForeignKeyConstraint(
            ['sucursal_id'],
            ['sucursal.id'],
            name=op.f('fk_promocion_sucursal_id_sucursal'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_promocion')),
    )
    # Todo pedido pregunta "que promociones corren para esta empresa": sin el
    # indice es un scan por cada venta que se confirma.
    op.create_index(op.f('ix_promocion_empresa_id'), 'promocion', ['empresa_id'])

    op.create_table(
        'venta_promocion',
        sa.Column('venta_id', sa.Uuid(), nullable=False),
        sa.Column('promocion_id', sa.Uuid(), nullable=False),
        sa.Column('nombre', sa.String(length=120), nullable=False),
        sa.Column('monto', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('detalle', JSONB, nullable=True),
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
            ['promocion_id'],
            ['promocion.id'],
            name=op.f('fk_venta_promocion_promocion_id_promocion'),
        ),
        sa.ForeignKeyConstraint(
            ['venta_id'], ['venta.id'], name=op.f('fk_venta_promocion_venta_id_venta')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_venta_promocion')),
    )
    op.create_index(
        op.f('ix_venta_promocion_venta_id'), 'venta_promocion', ['venta_id']
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_venta_promocion_venta_id'), table_name='venta_promocion')
    op.drop_table('venta_promocion')
    op.drop_index(op.f('ix_promocion_empresa_id'), table_name='promocion')
    op.drop_table('promocion')
