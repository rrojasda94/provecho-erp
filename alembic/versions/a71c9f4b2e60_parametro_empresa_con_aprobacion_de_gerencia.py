"""parametro_empresa: valor configurable por empresa con aprobación de Gerencia

Revision ID: a71c9f4b2e60
Revises: c9a2f4e18b60
Create Date: 2026-08-02 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'a71c9f4b2e60'
down_revision: str | None = 'b1d09e574c23'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'parametro_empresa',
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column('modulo', sa.String(length=50), nullable=False),
        sa.Column('codigo', sa.String(length=50), nullable=False),
        sa.Column('valor', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
        sa.Column('estado', sa.Enum('propuesto', 'vigente', 'rechazado', 'reemplazado', name='estado_parametro_empresa', native_enum=False), nullable=False),
        sa.Column('propuesto_por_id', sa.Uuid(), nullable=False),
        sa.Column('motivo', sa.Text(), nullable=True),
        sa.Column('resuelto_por_id', sa.Uuid(), nullable=True),
        sa.Column('resuelto_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('motivo_rechazo', sa.Text(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id'], name=op.f('fk_parametro_empresa_empresa_id_empresa')),
        sa.ForeignKeyConstraint(['propuesto_por_id'], ['usuario.id'], name=op.f('fk_parametro_empresa_propuesto_por_id_usuario')),
        sa.ForeignKeyConstraint(['resuelto_por_id'], ['usuario.id'], name=op.f('fk_parametro_empresa_resuelto_por_id_usuario')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_parametro_empresa')),
    )
    # Un solo valor vigente por empresa/modulo/codigo; propuestas e historial
    # conviven en la misma tabla sin chocar.
    op.create_index(
        'uq_parametro_empresa_vigente',
        'parametro_empresa',
        ['empresa_id', 'modulo', 'codigo'],
        unique=True,
        postgresql_where=sa.text("estado = 'vigente'"),
        sqlite_where=sa.text("estado = 'vigente'"),
    )


def downgrade() -> None:
    op.drop_index('uq_parametro_empresa_vigente', table_name='parametro_empresa')
    op.drop_table('parametro_empresa')
