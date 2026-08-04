"""nota de credito: documento afectado, motivo y series propias

Revision ID: c2f7a91b4e08
Revises: f3a1c62d90b4
Create Date: 2026-08-04 23:40:00.000000

Anular una venta ya cobrada no es borrarla: es emitir una nota de crédito
que la corrige (RN-CPP-009). Esta migración agrega lo que ese documento
necesita y no existía:

- `comprobante.afecta_comprobante_id` — a qué documento corrige. Una NC sin
  documento afectado la rechaza SUNAT y contablemente no dice nada.
- `comprobante.motivo_nc` / `motivo_nc_descripcion` — código del catálogo 09
  y su texto.
- `comprobante.detalle_nc` — qué líneas y cuánto, cuando la NC es parcial.
- `comprobante.anulado_por_nc_id` — se llena en el comprobante AFECTADO
  cuando su NC total es aceptada: es lo que impide volver a acreditarlo y lo
  que habilita reemitir el corregido.
- `punto_venta.serie_nc_boleta` / `serie_nc_factura` — la NC numera aparte
  del documento que corrige. Nullable: los puntos de venta existentes no las
  tenían, y sin serie el ERP no emite y lo dice, en vez de inventar una.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'c2f7a91b4e08'
down_revision: str | None = 'f3a1c62d90b4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    op.add_column('comprobante', sa.Column('afecta_comprobante_id', sa.Uuid(), nullable=True))
    op.add_column('comprobante', sa.Column('motivo_nc', sa.String(length=2), nullable=True))
    op.add_column(
        'comprobante', sa.Column('motivo_nc_descripcion', sa.String(length=255), nullable=True)
    )
    op.add_column('comprobante', sa.Column('detalle_nc', _JSONB, nullable=True))
    op.add_column('comprobante', sa.Column('anulado_por_nc_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f('fk_comprobante_afecta_comprobante_id_comprobante'),
        'comprobante', 'comprobante', ['afecta_comprobante_id'], ['id'],
    )
    op.create_foreign_key(
        op.f('fk_comprobante_anulado_por_nc_id_comprobante'),
        'comprobante', 'comprobante', ['anulado_por_nc_id'], ['id'],
    )
    op.add_column('punto_venta', sa.Column('serie_nc_boleta', sa.String(length=10), nullable=True))
    op.add_column('punto_venta', sa.Column('serie_nc_factura', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column('punto_venta', 'serie_nc_factura')
    op.drop_column('punto_venta', 'serie_nc_boleta')
    op.drop_constraint(
        op.f('fk_comprobante_anulado_por_nc_id_comprobante'), 'comprobante', type_='foreignkey'
    )
    op.drop_constraint(
        op.f('fk_comprobante_afecta_comprobante_id_comprobante'), 'comprobante', type_='foreignkey'
    )
    op.drop_column('comprobante', 'anulado_por_nc_id')
    op.drop_column('comprobante', 'detalle_nc')
    op.drop_column('comprobante', 'motivo_nc_descripcion')
    op.drop_column('comprobante', 'motivo_nc')
    op.drop_column('comprobante', 'afecta_comprobante_id')
