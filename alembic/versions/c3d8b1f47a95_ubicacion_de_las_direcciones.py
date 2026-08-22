"""ubicacion de las direcciones

Ancla las direcciones de texto a un punto real del mapa (ADR-053): place_id
de Google, coordenadas, plus code y distrito. El texto sigue viviendo en la
columna que cada tabla ya tenia (`direccion`, `domicilio`,
`domicilio_fiscal`); esto se le suma.

Todo nullable: las filas que ya existen no tienen coordenadas y siguen siendo
validas, y una direccion escrita a mano tambien lo es.

`distrito` es lo que decide si un reparto cae en zona restringida (ADR-054)
sin traer geometria ni PostGIS al proyecto.

Revision ID: c3d8b1f47a95
Revises: b5f27ac41e83
Create Date: 2026-08-22

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c3d8b1f47a95'
down_revision: str | None = 'b5f27ac41e83'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLAS = ('sucursal', 'almacen', 'empresa', 'persona', 'proveedor')

COLUMNAS = (
    ('ubicacion_place_id', sa.String(length=255)),
    # 6 decimales ~ 11 cm en el ecuador: de sobra para una puerta.
    ('ubicacion_lat', sa.Numeric(9, 6)),
    ('ubicacion_lng', sa.Numeric(9, 6)),
    ('ubicacion_plus_code', sa.String(length=20)),
    ('ubicacion_distrito', sa.String(length=100)),
)


def upgrade() -> None:
    for tabla in TABLAS:
        for nombre, tipo in COLUMNAS:
            op.add_column(tabla, sa.Column(nombre, tipo, nullable=True))


def downgrade() -> None:
    for tabla in reversed(TABLAS):
        for nombre, _ in reversed(COLUMNAS):
            op.drop_column(tabla, nombre)
