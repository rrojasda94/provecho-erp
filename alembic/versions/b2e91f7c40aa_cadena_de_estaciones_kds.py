"""cadena de estaciones del KDS

Revision ID: b2e91f7c40aa
Revises: a7c04e3b91d5
Create Date: 2026-08-13 09:20:00.000000

Dos columnas que son la misma idea: la cocina deja de ser un solo paso.

- `kds_pantalla.orden`: eslabón de la estación en la cadena de preparación
  (armado → horno → …). NOT NULL con default 0 — una cocina de una sola
  estación es una cadena de un eslabón, así que todo lo ya configurado
  queda exactamente como estaba.
- `venta_item.etapa_kds`: en qué eslabón va la línea. Mismo default por el
  mismo motivo: los pedidos en vuelo durante el despliegue siguen su curso
  en la primera estación que los acepte.

No es FK a `kds_pantalla` a propósito (ADR-044): la línea guarda dónde va,
no quién la atiende. Desactivar el horno a media noche no puede dejar
pedidos apuntando a una pantalla que ya no existe.

Sin backfill: el default 0 es el valor correcto para todo lo que ya estaba.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b2e91f7c40aa'
down_revision: str | None = 'a7c04e3b91d5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'kds_pantalla',
        sa.Column('orden', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'venta_item',
        sa.Column('etapa_kds', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('venta_item', 'etapa_kds')
    op.drop_column('kds_pantalla', 'orden')
