"""comprobante gravado_igv

La operacion que si lleva IGV aunque la empresa venda exonerada (ADR-080):

- `comprobante.gravado_igv`: NULL = decide el default de la empresa
  (`empresa.config_fiscal["igv_por_defecto"]`, y si tampoco esta, la zona
  tributaria). Nullable a proposito: todo lo ya emitido conserva el
  regimen con el que se emitio, que es el default de su empresa.

Vive en `comprobante` y no en `venta` ni en `orden_compra` porque el IGV
nace con el comprobante: el credito fiscal se toma con el comprobante
anotado y el debito con el emitido.

Revision ID: dfb195b14433
Revises: a1c9e5f2b364
Create Date: 2026-08-29

"""
from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = 'dfb195b14433'
down_revision: str | None = 'a1c9e5f2b364'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('comprobante', sa.Column('gravado_igv', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('comprobante', 'gravado_igv')
