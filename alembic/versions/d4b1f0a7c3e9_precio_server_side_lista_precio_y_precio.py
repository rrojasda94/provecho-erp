"""precio server-side: lista_precio y precio (RN-PRC-003)

Revision ID: d4b1f0a7c3e9
Revises: e5a1c93b7d40
Create Date: 2026-07-27 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'd4b1f0a7c3e9'
down_revision: str | None = 'e5a1c93b7d40'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'lista_precio',
        sa.Column('marca_id', sa.Uuid(), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('sucursal_id', sa.Uuid(), nullable=True),
        sa.Column('canal', sa.Enum('pdv', 'agente_ia', 'delivery', name='canal_lista_precio', native_enum=False), nullable=True),
        sa.Column('modalidad', sa.Enum('mesa', 'takeout', 'delivery', name='modalidad_lista_precio', native_enum=False), nullable=True),
        sa.Column('es_promocional', sa.Boolean(), nullable=False),
        sa.Column('vigente_desde', sa.Date(), nullable=False),
        sa.Column('vigente_hasta', sa.Date(), nullable=True),
        sa.Column('activa', sa.Boolean(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['marca_id'], ['marca.id'], name=op.f('fk_lista_precio_marca_id_marca')),
        sa.ForeignKeyConstraint(['sucursal_id'], ['sucursal.id'], name=op.f('fk_lista_precio_sucursal_id_sucursal')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_lista_precio')),
    )
    op.create_table(
        'precio',
        sa.Column('lista_precio_id', sa.Uuid(), nullable=False),
        sa.Column('producto_comercial_id', sa.Uuid(), nullable=False),
        sa.Column('monto', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['lista_precio_id'], ['lista_precio.id'], name=op.f('fk_precio_lista_precio_id_lista_precio')),
        sa.ForeignKeyConstraint(['producto_comercial_id'], ['producto_comercial.id'], name=op.f('fk_precio_producto_comercial_id_producto_comercial')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_precio')),
        sa.UniqueConstraint('lista_precio_id', 'producto_comercial_id', name=op.f('uq_precio_lista_precio_id')),
    )
    # La columna ya existía sin FK esperando esta tabla (RN-MDP-001).
    # `batch_alter_table`: SQLite no sabe hacer ALTER de constraints, así que
    # la migración solo se puede verificar en seco si pasa por batch mode.
    with op.batch_alter_table('medio_pago') as batch:
        batch.create_foreign_key(
            op.f('fk_medio_pago_lista_precio_credito_id_lista_precio'),
            'lista_precio', ['lista_precio_credito_id'], ['id'],
        )


def downgrade() -> None:
    with op.batch_alter_table('medio_pago') as batch:
        batch.drop_constraint(
            op.f('fk_medio_pago_lista_precio_credito_id_lista_precio'),
            type_='foreignkey',
        )
    op.drop_table('precio')
    op.drop_table('lista_precio')
