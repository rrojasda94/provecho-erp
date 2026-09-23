"""asiento_omitido: motivo 'error' para los listeners que revientan

Un listener contable que fallaba con una excepción solo dejaba rastro en el
log: la pantalla de Asientos no se enteraba y el balance quedaba corto sin
decir de qué operación. Ahora se anota con motivo `error` y el mensaje.

Revision ID: d8e2f4a6b1c3
Revises: b3c81d4e9a17
Create Date: 2026-09-23 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str = "d8e2f4a6b1c3"
down_revision: str | None = "b3c81d4e9a17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("motivo_asiento_omitido", "asiento_omitido", type_="check")
    op.create_check_constraint(
        "motivo_asiento_omitido",
        "asiento_omitido",
        sa.text("motivo IN ('periodo_cerrado', 'sin_cuentas', 'sin_plantilla', 'error')"),
    )


def downgrade() -> None:
    op.execute("DELETE FROM asiento_omitido WHERE motivo = 'error'")
    op.drop_constraint("motivo_asiento_omitido", "asiento_omitido", type_="check")
    op.create_check_constraint(
        "motivo_asiento_omitido",
        "asiento_omitido",
        sa.text("motivo IN ('periodo_cerrado', 'sin_cuentas', 'sin_plantilla')"),
    )
