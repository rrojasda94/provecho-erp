"""preferencias de presentacion del usuario

Tres columnas con `server_default`: las filas existentes quedan en el valor
estándar sin backfill, y una inserción escrita antes de esta migración sigue
siendo válida.

`native_enum=False` (CHECK + VARCHAR, no un tipo ENUM de Postgres) por la
misma razón que el resto del ERP: agregar un valor a un ENUM nativo es un
`ALTER TYPE` que no corre dentro de una transacción y no se puede revertir.

Revision ID: df7fa09a4f62
Revises: c1e64a9f7b28
Create Date: 2026-08-12 14:46:48.057447

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "df7fa09a4f62"
down_revision: str | None = "c1e64a9f7b28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column(
            "preferencia_paleta",
            sa.Enum(
                "estandar",
                "alto_contraste",
                name="preferencia_paleta",
                native_enum=False,
            ),
            server_default="estandar",
            nullable=False,
        ),
    )
    op.add_column(
        "usuario",
        sa.Column(
            "preferencia_tamano_fuente",
            sa.Enum(
                "estandar",
                "grande",
                "muy_grande",
                "maximo",
                name="preferencia_tamano_fuente",
                native_enum=False,
            ),
            server_default="estandar",
            nullable=False,
        ),
    )
    op.add_column(
        "usuario",
        sa.Column(
            "preferencia_tema",
            sa.Enum("claro", "oscuro", name="preferencia_tema", native_enum=False),
            server_default="claro",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("usuario", "preferencia_tema")
    op.drop_column("usuario", "preferencia_tamano_fuente")
    op.drop_column("usuario", "preferencia_paleta")
