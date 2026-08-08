"""token de API para cuentas agente_ia

Revision ID: b3f7d21a9c04
Revises: c1f80b6a2d34
Create Date: 2026-08-08 10:00:00.000000

Un agente (n8n, el bot de pedidos, el hub de sucursal) no teclea un PIN de
6 dígitos ni refresca una sesión cada 15 minutos: eso es ceremonia humana.
`token_agente` es su credencial de larga vida — cadena aleatoria de 256
bits, guardada solo como SHA-256 (igual que `refresh_token`), con `prefijo`
visible para poder decir *cuál* revocar.

Solo la tabla es nueva: los roles, permisos y sucursales del agente son los
de siempre. El token dice quién es; el RBAC sigue diciendo qué puede.

El CRUD de organización que entra en la misma versión **no toca el
esquema**: `grupo`, `empresa`, `marca`, `licencia_marca`, `sucursal` y
`almacen` ya existían y hasta ahora solo los escribía el seeder.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b3f7d21a9c04'
down_revision: str | None = 'c1f80b6a2d34'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'token_agente',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('usuario_id', sa.Uuid(), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('prefijo', sa.String(length=16), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expira_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revocado', sa.Boolean(), nullable=False),
        sa.Column('ultimo_uso_en', sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index(
        op.f('ix_token_agente_prefijo'), 'token_agente', ['prefijo'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_token_agente_prefijo'), table_name='token_agente')
    op.drop_table('token_agente')
