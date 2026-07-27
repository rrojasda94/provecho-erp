"""sync_watermark: motor de sync del hub de sucursal (ADR-009 fase 2)

Unica tabla que el motor de sync agrega al esquema. Solo la escribe un hub
(una fila por recurso y direccion); en la nube queda vacia. No es un outbox:
guarda hasta donde sincronizo cada recurso, no una fila por escritura.

Revision ID: e5c47b90f118
Revises: dad43729501d
Create Date: 2026-07-27

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e5c47b90f118'
down_revision: str | None = 'dad43729501d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'sync_watermark',
        sa.Column('direccion', sa.String(length=10), nullable=False),
        sa.Column('recurso', sa.String(length=50), nullable=False),
        sa.Column('marca', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ultimo_ok', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ultimo_error', sa.String(length=500), nullable=True),
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
        sa.PrimaryKeyConstraint('direccion', 'recurso', name=op.f('pk_sync_watermark')),
    )


def downgrade() -> None:
    op.drop_table('sync_watermark')
