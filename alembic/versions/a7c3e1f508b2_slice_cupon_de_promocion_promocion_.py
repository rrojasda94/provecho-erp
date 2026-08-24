"""slice cupón de promoción: promocion_cupon y cupon

Revision ID: a7c3e1f508b2
Revises: e2b7c40d91af
Create Date: 2026-08-24 10:00:00.000000

Las dos tablas de la campaña «Queremos RE-conocerte» (ADR-060): la landing
pública del QR registra al cliente y le emite un cupón de un solo uso, que
la caja canjea contra su siguiente venta.

Las dos cuelgan de `grupo_id` (transitivamente, en el caso de `cupon`, por
su `cliente_id`) y no de `empresa_id`: el cupón se le da a un `cliente`, que
es transversal al grupo (RN-PTS-001). Un cupón por empresa dejaría al
cliente sin poder usarlo en el local de al lado.

Los dos únicos de `cupon` llevan nombre a mano porque los dos empiezan por
`promocion_id` y la convención los armaría con el mismo nombre.

La fila de la promoción NO va acá: es dato de negocio y la crea el seeder.
Insertarla en la migración la resucitaría en cada `downgrade`/`upgrade`,
incluso después de que alguien la terminó a propósito.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a7c3e1f508b2'
down_revision: str | None = 'e2b7c40d91af'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'promocion_cupon',
        sa.Column('grupo_id', sa.Uuid(), nullable=False),
        sa.Column('nombre', sa.String(length=120), nullable=False),
        sa.Column('descuento_porcentaje', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('vigente_hasta', sa.Date(), nullable=False),
        sa.Column('vigencia_cupon_dias', sa.Integer(), nullable=False),
        sa.Column('estado', sa.Enum('activa', 'terminada', name='estado_promocion_cupon', native_enum=False), nullable=False),
        sa.Column('terminada_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('terminada_por', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['grupo_id'], ['grupo.id'], name=op.f('fk_promocion_cupon_grupo_id_grupo')),
        sa.ForeignKeyConstraint(['terminada_por'], ['usuario.id'], name=op.f('fk_promocion_cupon_terminada_por_usuario')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_promocion_cupon')),
        sa.UniqueConstraint('grupo_id', 'nombre', name=op.f('uq_promocion_cupon_grupo_id')),
    )
    op.create_table(
        'cupon',
        sa.Column('promocion_id', sa.Uuid(), nullable=False),
        sa.Column('cliente_id', sa.Uuid(), nullable=False),
        sa.Column('codigo', sa.String(length=20), nullable=False),
        sa.Column('estado', sa.Enum('activo', 'canjeado', name='estado_cupon', native_enum=False), nullable=False),
        sa.Column('vigente_hasta', sa.Date(), nullable=False),
        sa.Column('venta_id', sa.Uuid(), nullable=True),
        sa.Column('canjeado_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('canjeado_por', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['canjeado_por'], ['usuario.id'], name=op.f('fk_cupon_canjeado_por_usuario')),
        sa.ForeignKeyConstraint(['cliente_id'], ['cliente.id'], name=op.f('fk_cupon_cliente_id_cliente')),
        sa.ForeignKeyConstraint(['promocion_id'], ['promocion_cupon.id'], name=op.f('fk_cupon_promocion_id_promocion_cupon')),
        sa.ForeignKeyConstraint(['venta_id'], ['venta.id'], name=op.f('fk_cupon_venta_id_venta')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_cupon')),
        sa.UniqueConstraint('promocion_id', 'cliente_id', name='uq_cupon_promocion_cliente'),
        sa.UniqueConstraint('promocion_id', 'codigo', name='uq_cupon_promocion_codigo'),
    )
    # `cupon.cliente_id` ya lo cubre el único de (promocion_id, cliente_id).
    # Estos dos son las FK que sí se consultan sueltas: la venta al leer qué
    # cupón la descontó, y el usuario al auditar quién canjeó.
    op.create_index(op.f('ix_cupon_venta_id'), 'cupon', ['venta_id'])
    op.create_index(op.f('ix_promocion_cupon_grupo_id'), 'promocion_cupon', ['grupo_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_promocion_cupon_grupo_id'), table_name='promocion_cupon')
    op.drop_index(op.f('ix_cupon_venta_id'), table_name='cupon')
    op.drop_table('cupon')
    op.drop_table('promocion_cupon')
