"""comprobante: emision electronica (Factiliza)

Reemplaza las columnas atadas a Nubefact (proveedor descartado) por un
estado de emision neutral, mas hash/detalle/intentos para operar la cola.

Revision ID: b3d7f21ac094
Revises: 9e1b6a4c7d23
Create Date: 2026-07-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b3d7f21ac094'
down_revision: str | None = '9e1b6a4c7d23'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ESTADO_EMISION = sa.Enum(
    'no_aplica',
    'pendiente',
    'aceptado',
    'rechazado',
    'error',
    name='estado_emision_comprobante',
    native_enum=False,
)


def upgrade() -> None:
    op.drop_column('comprobante', 'estado_nubefact')
    op.drop_column('comprobante', 'respuesta_nubefact')
    op.add_column(
        'comprobante',
        sa.Column(
            'estado_emision',
            _ESTADO_EMISION,
            nullable=False,
            server_default='no_aplica',
        ),
    )
    op.add_column(
        'comprobante', sa.Column('hash_proveedor', sa.String(length=120), nullable=True)
    )
    op.add_column('comprobante', sa.Column('detalle_emision', sa.Text(), nullable=True))
    op.add_column(
        'comprobante',
        sa.Column('intentos_emision', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'comprobante', sa.Column('respuesta_proveedor', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('comprobante', 'respuesta_proveedor')
    op.drop_column('comprobante', 'intentos_emision')
    op.drop_column('comprobante', 'detalle_emision')
    op.drop_column('comprobante', 'hash_proveedor')
    op.drop_column('comprobante', 'estado_emision')
    op.add_column(
        'comprobante', sa.Column('estado_nubefact', sa.String(length=30), nullable=True)
    )
    op.add_column(
        'comprobante', sa.Column('respuesta_nubefact', sa.JSON(), nullable=True)
    )
