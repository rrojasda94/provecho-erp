"""storefront_cuenta: debe_cambiar_clave

Atención al cliente puede restablecer la clave de una cuenta del sitio y darle
una temporal. `debe_cambiar_clave` obliga a quien entra con ella a elegir una
propia antes de seguir. NOT NULL con default falso: las cuentas existentes no
tienen nada pendiente.

Revision ID: cec53f7b2f6e
Revises: 5c1a7e90d4b3
Create Date: 2026-09-19 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str = "cec53f7b2f6e"
down_revision: str | None = "5c1a7e90d4b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "storefront_cuenta",
        sa.Column(
            "debe_cambiar_clave", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("storefront_cuenta", "debe_cambiar_clave")
