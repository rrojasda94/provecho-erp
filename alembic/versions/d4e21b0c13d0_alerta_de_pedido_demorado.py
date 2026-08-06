"""alerta de pedido demorado

Revision ID: d4e21b0c13d0
Revises: 5e1c7775f6ca
Create Date: 2026-08-04 10:30:52.964050

`UNIQUE (venta_id, minutos_umbral)` no es cosmético: es lo que hace segura
la convivencia de la revisión puntual (agendada al confirmar la venta) con
el barrido periódico. Dos workers mirando el mismo pedido a la vez no
pueden crear dos alertas.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd4e21b0c13d0'
down_revision: str | None = '5e1c7775f6ca'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'alerta_pedido',
        sa.Column('venta_id', sa.Uuid(), nullable=False),
        sa.Column('sucursal_id', sa.Uuid(), nullable=False),
        sa.Column('minutos_umbral', sa.Integer(), nullable=False),
        sa.Column('minutos_transcurridos', sa.Numeric(8, 2), nullable=False),
        sa.Column('estado_al_alertar', sa.String(length=20), nullable=False),
        sa.Column('items_pendientes', sa.Integer(), nullable=False),
        sa.Column('atendida_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('atendida_por', sa.Uuid(), nullable=True),
        sa.Column('nota', sa.String(length=300), nullable=True),
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
            ['venta_id'], ['venta.id'], name=op.f('fk_alerta_pedido_venta_id_venta')
        ),
        sa.ForeignKeyConstraint(
            ['sucursal_id'],
            ['sucursal.id'],
            name=op.f('fk_alerta_pedido_sucursal_id_sucursal'),
        ),
        sa.ForeignKeyConstraint(
            ['atendida_por'],
            ['usuario.id'],
            name=op.f('fk_alerta_pedido_atendida_por_usuario'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_alerta_pedido')),
        sa.UniqueConstraint('venta_id', 'minutos_umbral', name='uq_alerta_pedido_venta'),
    )
    op.create_index(op.f('ix_alerta_pedido_venta_id'), 'alerta_pedido', ['venta_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_alerta_pedido_venta_id'), table_name='alerta_pedido')
    op.drop_table('alerta_pedido')
