"""asiento_omitido: el asiento automático que no se escribió, y por qué

El asiento automático nunca bloquea la operación de origen, y esa decisión
se mantiene. Lo que faltaba era el rastro: hasta el 2026-09-05 la omisión
salía por `log.info` con un motivo equivocado, así que un balance vacío no
tenía cómo explicarse. Misma forma y mismo criterio que
`incidencia_inventario` (ADR-089).

Revision ID: b5e7d1a3c92f
Revises: 12f51f21f27e
Create Date: 2026-09-05 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'b5e7d1a3c92f'
down_revision: str | None = '12f51f21f27e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'asiento_omitido',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column('evento', sa.String(length=64), nullable=False),
        sa.Column('referencia_origen', sa.String(length=64), nullable=False),
        sa.Column(
            'motivo',
            sa.Enum(
                'periodo_cerrado',
                'sin_cuentas',
                'sin_plantilla',
                name='motivo_asiento_omitido',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('detalle', sa.String(length=300), nullable=True),
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
        sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_asiento_omitido_empresa_id'), 'asiento_omitido', ['empresa_id']
    )
    op.create_index(op.f('ix_asiento_omitido_evento'), 'asiento_omitido', ['evento'])
    op.create_index(op.f('ix_asiento_omitido_fecha'), 'asiento_omitido', ['fecha'])
    op.create_index(
        op.f('ix_asiento_omitido_referencia_origen'),
        'asiento_omitido',
        ['referencia_origen'],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_asiento_omitido_referencia_origen'), 'asiento_omitido')
    op.drop_index(op.f('ix_asiento_omitido_fecha'), 'asiento_omitido')
    op.drop_index(op.f('ix_asiento_omitido_evento'), 'asiento_omitido')
    op.drop_index(op.f('ix_asiento_omitido_empresa_id'), 'asiento_omitido')
    op.drop_table('asiento_omitido')
