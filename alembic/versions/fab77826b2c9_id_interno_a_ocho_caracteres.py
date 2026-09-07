"""id_interno pasa de 4 a 8 caracteres, sigue único en todo el grupo

`articulo.id_interno` y `producto_comercial.id_interno` eran 4 caracteres
alfanuméricos compartidos entre TODAS las empresas del grupo (no por
empresa — decisión 2026-09-06, ver ADR-091): un catálogo de trescientos
artículos agotaba rápido ese espacio. Se ensancha la columna; los códigos
ya asignados de 4 caracteres siguen valiendo sin tocarse.

Revision ID: fab77826b2c9
Revises: 4466bd44b238
Create Date: 2026-09-06 12:31:08.523230

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "fab77826b2c9"
down_revision: str | None = "4466bd44b238"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "articulo", "id_interno",
        existing_type=sa.VARCHAR(length=4),
        type_=sa.String(length=8),
        existing_nullable=False,
    )
    op.alter_column(
        "producto_comercial", "id_interno",
        existing_type=sa.VARCHAR(length=4),
        type_=sa.String(length=8),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "producto_comercial", "id_interno",
        existing_type=sa.String(length=8),
        type_=sa.VARCHAR(length=4),
        existing_nullable=False,
    )
    op.alter_column(
        "articulo", "id_interno",
        existing_type=sa.String(length=8),
        type_=sa.VARCHAR(length=4),
        existing_nullable=False,
    )
