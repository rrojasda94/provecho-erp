"""notificacion en bandeja

Revision ID: 7fda1eb759f7
Revises: d4e21b0c13d0
Create Date: 2026-08-04 12:08:05.724593

Bandeja de avisos por usuario. `referencia_tipo`/`referencia_id` son
polimórficos y **sin FK** a propósito: la notificación es transversal y no
puede tener una FK hacia `venta`, `alerta_pedido` y todo lo que venga —
mismo criterio que `decision_gerencial`.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '7fda1eb759f7'
down_revision: str | None = 'd4e21b0c13d0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'notificacion',
        sa.Column('usuario_id', sa.Uuid(), nullable=False),
        sa.Column('tipo', sa.String(length=60), nullable=False),
        sa.Column('nivel', sa.String(length=10), nullable=False),
        sa.Column('titulo', sa.String(length=150), nullable=False),
        sa.Column('cuerpo', sa.Text(), nullable=True),
        sa.Column('referencia_tipo', sa.String(length=50), nullable=True),
        sa.Column('referencia_id', sa.Uuid(), nullable=True),
        sa.Column('sucursal_id', sa.Uuid(), nullable=True),
        sa.Column('leida_at', sa.DateTime(timezone=True), nullable=True),
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
            ['usuario_id'],
            ['usuario.id'],
            name=op.f('fk_notificacion_usuario_id_usuario'),
        ),
        sa.ForeignKeyConstraint(
            ['sucursal_id'],
            ['sucursal.id'],
            name=op.f('fk_notificacion_sucursal_id_sucursal'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_notificacion')),
    )
    # La consulta que corre en cada carga de pantalla: "mis no leídas".
    op.create_index(
        'ix_notificacion_bandeja', 'notificacion', ['usuario_id', 'leida_at']
    )


def downgrade() -> None:
    op.drop_index('ix_notificacion_bandeja', table_name='notificacion')
    op.drop_table('notificacion')
