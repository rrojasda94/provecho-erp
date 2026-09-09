"""canal email en reports

Revision ID: 568b2a1dfcca
Revises: e5b094528cc9
Create Date: 2026-09-09 16:03:00.633420

"""

from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = "568b2a1dfcca"
down_revision: str | None = "e5b094528cc9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Autogenerate no compara el cuerpo de un CheckConstraint existente: el
    # canal 'email' (ADR-033) se agrega a mano en las dos tablas que lo
    # restringen.
    op.drop_constraint("canal_regla", "regla_distribucion", type_="check")
    op.create_check_constraint("canal_regla", "regla_distribucion", "canal IN ('bandeja', 'email')")
    op.drop_constraint("canal_entrega", "entrega_reporte", type_="check")
    op.create_check_constraint("canal_entrega", "entrega_reporte", "canal IN ('bandeja', 'email')")


def downgrade() -> None:
    op.drop_constraint("canal_entrega", "entrega_reporte", type_="check")
    op.create_check_constraint("canal_entrega", "entrega_reporte", "canal IN ('bandeja')")
    op.drop_constraint("canal_regla", "regla_distribucion", type_="check")
    op.create_check_constraint("canal_regla", "regla_distribucion", "canal IN ('bandeja')")
