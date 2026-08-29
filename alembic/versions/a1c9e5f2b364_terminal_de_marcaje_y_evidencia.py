"""terminal de marcaje y evidencia de marcacion

Ancla el marcaje de asistencia al dispositivo, no a la red (ADR-079):

- `terminal_marcaje`: el dispositivo autorizado a marcar por una sucursal.
  Nace inactivo con un codigo de activacion; enrolar lo activa y guarda
  solo el hash del secreto.
- `marcacion`: una fila por cada toque del pad, con su evidencia (quien
  firmo, desde que terminal, con que IP, a que distancia del local, con
  que foto). `asistencia` sigue siendo la fila-resumen del dia.
- `sucursal.radio_marcaje_m`: el radio en metros para observar (nunca
  bloquear) la distancia del marcaje. NULL = esa sucursal no lo evalua.

Revision ID: a1c9e5f2b364
Revises: d4b7e91c2f80
Create Date: 2026-08-28

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a1c9e5f2b364'
down_revision: str | None = 'd4b7e91c2f80'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('sucursal', sa.Column('radio_marcaje_m', sa.Integer(), nullable=True))

    op.create_table(
        'terminal_marcaje',
        sa.Column('sucursal_id', sa.Uuid(), nullable=False),
        sa.Column('nombre', sa.String(length=80), nullable=False),
        sa.Column('codigo', sa.String(length=6), nullable=True),
        sa.Column('codigo_expira_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('secreto_hash', sa.String(length=64), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False),
        sa.Column('ultima_marcacion_en', sa.DateTime(timezone=True), nullable=True),
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
            ['sucursal_id'], ['sucursal.id'],
            name=op.f('fk_terminal_marcaje_sucursal_id_sucursal'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_terminal_marcaje')),
    )
    op.create_index(
        'uq_terminal_marcaje_vivo',
        'terminal_marcaje',
        ['sucursal_id', 'nombre'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
        sqlite_where=sa.text('deleted_at IS NULL'),
    )
    op.create_index(
        'uq_terminal_marcaje_secreto',
        'terminal_marcaje',
        ['secreto_hash'],
        unique=True,
        postgresql_where=sa.text('secreto_hash IS NOT NULL'),
        sqlite_where=sa.text('secreto_hash IS NOT NULL'),
    )

    op.create_table(
        'marcacion',
        sa.Column('asistencia_id', sa.Uuid(), nullable=False),
        sa.Column(
            'tipo',
            sa.Enum('entrada', 'salida', name='tipo_marcacion', native_enum=False),
            nullable=False,
        ),
        sa.Column('momento', sa.DateTime(timezone=True), nullable=False),
        sa.Column('usuario_id', sa.Uuid(), nullable=False),
        sa.Column('terminal_id', sa.Uuid(), nullable=True),
        sa.Column('ip', sa.String(length=45), nullable=True),
        sa.Column('ubicacion_lat', sa.Numeric(9, 6), nullable=True),
        sa.Column('ubicacion_lng', sa.Numeric(9, 6), nullable=True),
        sa.Column('distancia_m', sa.Integer(), nullable=True),
        sa.Column('foto', sa.LargeBinary(), nullable=True),
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
            ['asistencia_id'], ['asistencia.id'],
            name=op.f('fk_marcacion_asistencia_id_asistencia'),
        ),
        sa.ForeignKeyConstraint(
            ['usuario_id'], ['usuario.id'],
            name=op.f('fk_marcacion_usuario_id_usuario'),
        ),
        sa.ForeignKeyConstraint(
            ['terminal_id'], ['terminal_marcaje.id'],
            name=op.f('fk_marcacion_terminal_id_terminal_marcaje'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_marcacion')),
    )
    op.create_index(
        op.f('ix_marcacion_asistencia_id'), 'marcacion', ['asistencia_id']
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_marcacion_asistencia_id'), table_name='marcacion')
    op.drop_table('marcacion')
    op.drop_index('uq_terminal_marcaje_secreto', table_name='terminal_marcaje')
    op.drop_index('uq_terminal_marcaje_vivo', table_name='terminal_marcaje')
    op.drop_table('terminal_marcaje')
    op.drop_column('sucursal', 'radio_marcaje_m')
