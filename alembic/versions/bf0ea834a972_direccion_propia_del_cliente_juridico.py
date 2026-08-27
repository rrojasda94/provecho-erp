"""direccion propia del cliente juridico

Separa la direccion del `contacto` del cliente juridico (ADR-072): `contacto`
era a la vez telefono, correo y direccion de quien coordina, y hoy termina
impreso como direccion en la factura electronica sin serlo de verdad.

`direccion` es la columna nueva y `contacto` no se toca: las filas que ya
existen se siguen leyendo igual, con `direccion or contacto` como respaldo.

Suma tambien las cinco columnas de ancla al mapa del `UbicacionMixin`
(ADR-053) que las demas tablas de direccion ya tienen: hasta ahora el
cliente juridico no tenia donde anclar la suya.

Todo nullable, sin backfill: un geocode masivo se cobra por registro, mismo
criterio que ADR-053.

Revision ID: bf0ea834a972
Revises: c4d17b93e0af
Create Date: 2026-08-27

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'bf0ea834a972'
down_revision: str | None = 'c4d17b93e0af'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLA = 'cliente'

COLUMNAS = (
    ('direccion', sa.String(length=255)),
    ('ubicacion_place_id', sa.String(length=255)),
    # 6 decimales ~ 11 cm en el ecuador: de sobra para una puerta.
    ('ubicacion_lat', sa.Numeric(9, 6)),
    ('ubicacion_lng', sa.Numeric(9, 6)),
    ('ubicacion_plus_code', sa.String(length=20)),
    ('ubicacion_distrito', sa.String(length=100)),
)


def upgrade() -> None:
    for nombre, tipo in COLUMNAS:
        op.add_column(TABLA, sa.Column(nombre, tipo, nullable=True))


def downgrade() -> None:
    for nombre, _ in reversed(COLUMNAS):
        op.drop_column(TABLA, nombre)
