"""tablero de reportes guardado

Revision ID: 998e335369a1
Revises: b6d1e83f47ac
Create Date: 2026-08-04 08:33:14.622682

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '998e335369a1'
down_revision: str | None = 'b6d1e83f47ac'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'tablero',
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column('usuario_id', sa.Uuid(), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('predeterminado', sa.Boolean(), nullable=False),
        sa.Column(
            'tarjetas',
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
            nullable=False,
        ),
        sa.Column(
            'filtros',
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
            nullable=False,
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
            ['empresa_id'], ['empresa.id'], name=op.f('fk_tablero_empresa_id_empresa')
        ),
        sa.ForeignKeyConstraint(
            ['usuario_id'], ['usuario.id'], name=op.f('fk_tablero_usuario_id_usuario')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tablero')),
    )
    # Índice parcial: un solo tablero predeterminado por usuario, sin
    # impedir que tenga varios tableros guardados.
    op.create_index(
        'uq_tablero_predeterminado',
        'tablero',
        ['usuario_id'],
        unique=True,
        sqlite_where=sa.text('predeterminado = 1'),
        postgresql_where=sa.text('predeterminado'),
    )


def downgrade() -> None:
    op.drop_index(
        'uq_tablero_predeterminado',
        table_name='tablero',
        sqlite_where=sa.text('predeterminado = 1'),
        postgresql_where=sa.text('predeterminado'),
    )
    op.drop_table('tablero')
