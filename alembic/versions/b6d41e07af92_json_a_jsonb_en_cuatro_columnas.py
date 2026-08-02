"""json → jsonb en las cuatro columnas que quedaron con el tipo genérico

Los modelos declaran `JsonB` (`JSON().with_variant(JSONB(), "postgresql")`),
pero cuatro migraciones antiguas crearon la columna con `sa.JSON()` a secas.
Resultado: en Postgres quedaron como `json` mientras las otras 19 columnas
JSON del esquema son `jsonb`.

No es cosmético. `json` guarda el texto tal cual — conserva espacios, orden
de claves y duplicados — y **no admite los operadores ni los índices GIN de
`jsonb`**. Cualquier consulta futura sobre `boleta_pago.ingresos` o
`comprobante.respuesta_proveedor` tendría que castear en cada acceso.

Además dejaba `alembic check` en rojo permanente, y un chequeo que siempre
falla es un chequeo que nadie mira.

La conversión es segura: todo `json` válido es `jsonb` válido. Lo único que
se pierde es el formato textual original, que nadie usa.

Revision ID: b6d41e07af92
Revises: a3f0d29b6c81
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b6d41e07af92"
down_revision = "a3f0d29b6c81"
branch_labels = None
depends_on = None

COLUMNAS = (
    ("acta", "participantes", False),
    ("boleta_pago", "ingresos", False),
    ("boleta_pago", "descuentos", False),
    ("comprobante", "respuesta_proveedor", True),
)


def upgrade() -> None:
    for tabla, columna, nullable in COLUMNAS:
        op.alter_column(
            tabla,
            columna,
            existing_type=sa.JSON(),
            type_=postgresql.JSONB(),
            existing_nullable=nullable,
            postgresql_using=f"{columna}::jsonb",
        )


def downgrade() -> None:
    for tabla, columna, nullable in COLUMNAS:
        op.alter_column(
            tabla,
            columna,
            existing_type=postgresql.JSONB(),
            type_=sa.JSON(),
            existing_nullable=nullable,
            postgresql_using=f"{columna}::json",
        )
