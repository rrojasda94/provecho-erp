"""extras de producto comercial

Un extra es un `producto_comercial` con `es_extra=True` y su propia receta,
que se ejecuta en la sucursal y se suma a la del producto al que se agrega
(RN-COM-021, ADR-016). Modelarlo así en vez de como entidad aparte hace que
herede precio server-side por lista, aparición en la carta y descuento de
insumos por el mismo evento `sales.venta_confirmada`.

Lo propio del extra son dos cosas: a qué productos se puede agregar
(`producto_comercial_extra`) y de qué línea cuelga al venderse
(`venta_item.padre_venta_item_id`).

`es_extra` nace en False para todos los productos existentes: nada de lo ya
cargado cambia de comportamiento.

Revision ID: f2a8c15e94d7
Revises: e1c4a9d6b038
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f2a8c15e94d7"
down_revision = "e1c4a9d6b038"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column(
        "producto_comercial",
        sa.Column(
            "es_extra", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_table(
        "producto_comercial_extra",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "producto_comercial_id",
            UUID,
            sa.ForeignKey("producto_comercial.id"),
            nullable=False,
        ),
        sa.Column(
            "extra_id", UUID, sa.ForeignKey("producto_comercial.id"), nullable=False
        ),
        sa.Column("maximo", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "producto_comercial_id", "extra_id", name="uq_producto_extra"
        ),
    )
    op.add_column(
        "venta_item", sa.Column("padre_venta_item_id", UUID, nullable=True)
    )
    op.create_foreign_key(
        "fk_venta_item_padre",
        "venta_item",
        "venta_item",
        ["padre_venta_item_id"],
        ["id"],
    )
    op.create_index(
        "ix_venta_item_padre_venta_item_id", "venta_item", ["padre_venta_item_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_venta_item_padre_venta_item_id", table_name="venta_item")
    op.drop_constraint("fk_venta_item_padre", "venta_item", type_="foreignkey")
    op.drop_column("venta_item", "padre_venta_item_id")
    op.drop_table("producto_comercial_extra")
    op.drop_column("producto_comercial", "es_extra")
