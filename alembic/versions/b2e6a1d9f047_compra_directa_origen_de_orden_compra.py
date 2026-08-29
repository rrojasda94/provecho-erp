"""compra directa: columna origen en orden_compra

Compra a proveedor sustentada solo con el comprobante recibido, sin OC
previa (deuda reconocida en el README del slice). Se reutiliza la tabla
`orden_compra` con `origen='directa'` en vez de un modelo aparte: así el
evento `purchases.compra_recibida` sale con el mismo contrato que ya
consumen `inventory` y `accounting`, sin tocar esos listeners, y
`dar_conformidad_comprobante` funciona sin cambios (ADR-0XX).

Revision ID: b2e6a1d9f047
Revises: dfb195b14433
Create Date: 2026-08-29

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b2e6a1d9f047'
down_revision: str | None = 'dfb195b14433'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'orden_compra',
        sa.Column(
            'origen',
            sa.Enum('oc', 'directa', name='origen_orden_compra', native_enum=False),
            nullable=False,
            server_default='oc',
        ),
    )
    op.alter_column('orden_compra', 'origen', server_default=None)


def downgrade() -> None:
    op.drop_column('orden_compra', 'origen')
