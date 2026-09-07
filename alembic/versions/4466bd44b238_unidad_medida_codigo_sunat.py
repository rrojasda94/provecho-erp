"""unidad_medida.codigo_sunat: el código del catálogo 03 de SUNAT

Sin esta columna, `factiliza/guias.py::codigo_unidad` traduce el nombre de
la UdM con un diccionario de doce entradas y cae en "NIU" (unidad) si no lo
reconoce — una UdM propia como "Doypack 2kg" sale mal en la guía de
remisión sin avisar a nadie. Nullable y editable desde Catálogo: el
diccionario sigue siendo el valor de siembra mientras nadie lo llene.

Revision ID: 4466bd44b238
Revises: c7a1e94b2d38
Create Date: 2026-09-06 11:32:09.752547

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4466bd44b238"
down_revision: str | None = "c7a1e94b2d38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "unidad_medida", sa.Column("codigo_sunat", sa.String(length=3), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("unidad_medida", "codigo_sunat")
