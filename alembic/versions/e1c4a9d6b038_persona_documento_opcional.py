"""persona: documento opcional (cliente identificado por teléfono)

No todo cliente quiere dar su DNI en el mostrador, y negarse a registrarlo
por eso pierde la venta y el historial. `persona.numero_documento` y
`tipo_documento` pasan a nullable; el UNIQUE del número se conserva —
un índice único admite varios NULL.

Trabajador y usuario siguen exigiendo documento: esa validación vive en
`users.application.admin`, no en el esquema, porque `persona` es compartida
y no todos sus roles tienen la misma exigencia.

Un cliente sin documento (o con el genérico `00000000`) queda fuera de las
promociones para clientes registrados con documento (RN-PTS-002). La regla
es derivada — `rules.cliente_identificado` —, no una columna: guardar el
mismo hecho dos veces solo crea la ocasión de que se contradigan.

Revision ID: e1c4a9d6b038
Revises: d7e3b8c14f52
"""

import sqlalchemy as sa
from alembic import op

revision = "e1c4a9d6b038"
down_revision = "d7e3b8c14f52"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "persona",
        "numero_documento",
        existing_type=sa.String(length=20),
        nullable=True,
    )
    op.alter_column(
        "persona",
        "tipo_documento",
        existing_type=sa.Enum(
            "dni", "ce", "pasaporte", name="tipo_documento", native_enum=False
        ),
        nullable=True,
    )


def downgrade() -> None:
    """Revertir exige que no queden personas sin documento: el NOT NULL
    fallaría con ellas en la tabla. Se marcan con un genérico derivado del
    id para no violar el UNIQUE."""
    op.execute(
        """
        UPDATE persona
        SET numero_documento = 'SD-' || SUBSTR(CAST(id AS VARCHAR), 1, 17),
            tipo_documento = 'dni'
        WHERE numero_documento IS NULL
        """
    )
    op.alter_column(
        "persona",
        "tipo_documento",
        existing_type=sa.Enum(
            "dni", "ce", "pasaporte", name="tipo_documento", native_enum=False
        ),
        nullable=False,
    )
    op.alter_column(
        "persona",
        "numero_documento",
        existing_type=sa.String(length=20),
        nullable=False,
    )
