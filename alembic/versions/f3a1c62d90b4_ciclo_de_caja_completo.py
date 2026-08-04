"""ciclo de caja completo: pos_tarjeta y correcciones de cierre

Revision ID: f3a1c62d90b4
Revises: 7fda1eb759f7
Create Date: 2026-08-04 16:40:00.000000

Dos cambios del slice de caja completa (ADR-025):

- `pos_tarjeta`: inventario de terminales con serie y código de comercio
  (RN-POS-010). `sucursal_id` NULL identifica al terminal de emergencia del
  pool de contabilidad (RN-POS-009), por eso es nullable y no se puede
  reemplazar por una FK obligatoria.
- `cierre_caja.correcciones`: historial de reaperturas (RN-MDP-005). Un
  cierre con faltante se corrige dejando rastro, no reescribiendo el número.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'f3a1c62d90b4'
down_revision: str | None = '7fda1eb759f7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'pos_tarjeta',
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column('sucursal_id', sa.Uuid(), nullable=True),
        sa.Column('serie', sa.String(length=50), nullable=False),
        sa.Column('codigo_comercio', sa.String(length=50), nullable=False),
        sa.Column('operador', sa.String(length=50), nullable=True),
        sa.Column(
            'estado',
            sa.Enum(
                'operativo', 'averiado', 'baja',
                name='estado_pos_tarjeta',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('es_emergencia', sa.Boolean(), nullable=False),
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
            name=op.f('fk_pos_tarjeta_empresa_id_empresa'),
        ),
        sa.ForeignKeyConstraint(
            ['sucursal_id'],
            ['sucursal.id'],
            name=op.f('fk_pos_tarjeta_sucursal_id_sucursal'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_pos_tarjeta')),
        sa.UniqueConstraint('serie', name='uq_pos_tarjeta_serie'),
    )
    op.add_column(
        'cierre_caja',
        sa.Column(
            'correcciones',
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()), 'postgresql'
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('cierre_caja', 'correcciones')
    op.drop_table('pos_tarjeta')
