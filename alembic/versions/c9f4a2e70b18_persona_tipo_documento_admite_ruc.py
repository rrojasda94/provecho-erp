"""persona.tipo_documento admite ruc y se hace cumplir en la base

El formulario ofrecía «RUC» y la base nunca lo conoció. El `Enum` de
SQLAlchemy es `native_enum=False` y, desde SQLAlchemy 1.4,
`create_constraint` vale `False` por defecto: la columna es un `VARCHAR(9)`
pelado sin ningún CHECK. Así que el INSERT **entraba** —`ruc` mide 3 y cabe—
y lo que reventaba era la lectura: el `result_processor` levanta
`LookupError: 'ruc' is not among the defined enum values` y devuelve 500.

Eso no es un alta rechazada, es una fila envenenada: una sola persona con
`ruc` tumba `GET /personas`, `/personas/buscar` y cualquier consulta que
cargue esa `Persona`, para todos, hasta que se corrija la fila.

Esta revisión hace dos cosas. Sanea lo que haya quedado guardado, y **crea el
CHECK que nunca se emitió** (el modelo pasa a `create_constraint=True`). Con
el CHECK, el mismo error vuelve a ser lo que tenía que haber sido siempre: un
INSERT rechazado. Y como SQLite sí hace cumplir los CHECK, la suite de tests
—que corre sobre SQLite— deja de tapar este agujero.

No hay `ALTER COLUMN`: el valor más largo del vocabulario sigue siendo
`pasaporte` (9 caracteres), así que `VARCHAR(9)` ya alcanza.

Revision ID: c9f4a2e70b18
Revises: f74025d6c871
Create Date: 2026-08-30

"""

import sqlalchemy as sa
from alembic import op

revision = "c9f4a2e70b18"
down_revision = "f74025d6c871"
branch_labels = None
depends_on = None

TIPOS = ("dni", "ce", "pasaporte", "ruc")
TIPOS_PREVIOS = ("dni", "ce", "pasaporte")
ALIAS_CE = ("carne_extranjeria", "carnet_extranjeria")


def upgrade() -> None:
    # El tablero de contratación mandaba `carne_extranjeria`. En Postgres no
    # llegó a guardarse nunca (17 caracteres en un VARCHAR(9)), pero sí en
    # cualquier copia sobre SQLite, que ignora el largo. Sale barato y evita
    # que el CHECK falle al crearse contra una base así.
    op.execute(
        sa.text("UPDATE persona SET tipo_documento = 'ce' WHERE tipo_documento IN :alias")
        .bindparams(sa.bindparam("alias", value=ALIAS_CE, expanding=True))
    )
    # Cualquier otro valor fuera del vocabulario pasa a NULL: la columna lo
    # admite desde `e1c4a9d6b038` y la fila se conserva (no hay DELETE de
    # persona por diseño, ADR-011).
    op.execute(
        sa.text(
            "UPDATE persona SET tipo_documento = NULL "
            "WHERE tipo_documento IS NOT NULL AND tipo_documento NOT IN :tipos"
        ).bindparams(sa.bindparam("tipos", value=TIPOS, expanding=True))
    )
    op.create_check_constraint(
        "tipo_documento", "persona", sa.column("tipo_documento").in_(TIPOS)
    )


def downgrade() -> None:
    op.drop_constraint("tipo_documento", "persona", type_="check")
    op.execute("UPDATE persona SET tipo_documento = NULL WHERE tipo_documento = 'ruc'")
    op.create_check_constraint(
        "tipo_documento", "persona", sa.column("tipo_documento").in_(TIPOS_PREVIOS)
    )
