"""postulante.estado a VARCHAR(15) y baja del UNIQUE redundante de convocatoria

Dos derivas entre el modelo y el esquema que dejó el slice de contratación
(`a7f2c81e4b95`), y que `alembic check` venía marcando:

1. **`postulante.estado` seguía en VARCHAR(10)**. La columna nació con
   `Enum('en_proceso','rechazado','contratado')` — 10 caracteres el más
   largo — y el slice la pasó a nueve estados sin ensanchar el tipo: solo
   migró los datos. No es cosmética: en Postgres, mover un postulante a
   `preseleccionado` (15) u `oferta_enviada` (14) falla con
   `value too long for type character varying(10)`. Los tests no lo cazan
   porque SQLite ignora el largo de VARCHAR.

2. **`convocatoria.token_publico` tenía UNIQUE por duplicado**: una
   `UniqueConstraint` y además un índice único. El modelo declara
   `unique=True, index=True`, que SQLAlchemy resuelve como **un** índice
   único; la constraint sobraba y era la que `alembic check` reportaba.

Revision ID: e4a2f9c17b3d
Revises: b1d09e574c23
Create Date: 2026-08-02 17:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'e4a2f9c17b3d'
down_revision: str | None = 'b1d09e574c23'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ESTADOS_NUEVOS = (
    'recibido', 'preseleccionado', 'entrevistado', 'verificado',
    'oferta_enviada', 'contratado', 'inducido', 'confirmado', 'descartado',
)
_ESTADOS_VIEJOS = ('recibido', 'contratado', 'inducido', 'confirmado', 'descartado')


def upgrade() -> None:
    op.alter_column(
        'postulante',
        'estado',
        existing_type=sa.String(length=10),
        type_=sa.Enum(*_ESTADOS_NUEVOS, name='estado_postulante', native_enum=False),
        existing_nullable=False,
    )
    op.drop_constraint(
        op.f('uq_convocatoria_token_publico'), 'convocatoria', type_='unique'
    )


def downgrade() -> None:
    op.create_unique_constraint(
        op.f('uq_convocatoria_token_publico'), 'convocatoria', ['token_publico']
    )
    # Los estados que no entran en 10 caracteres vuelven al inicio del tablero:
    # el esquema viejo no puede representarlos y estrechar la columna con esos
    # valores dentro falla. Se pierde el avance, que es lo que un downgrade a un
    # esquema que no los conoce implica.
    op.execute(
        "UPDATE postulante SET estado = 'recibido' "
        f"WHERE estado NOT IN {_ESTADOS_VIEJOS}"
    )
    op.alter_column(
        'postulante',
        'estado',
        existing_type=sa.Enum(*_ESTADOS_NUEVOS, name='estado_postulante', native_enum=False),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
