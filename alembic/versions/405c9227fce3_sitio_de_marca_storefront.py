"""sitio de marca (storefront): contenido, descripciones y telefono de sucursal

Primer código del módulo `storefront` (ADR-103, PR1 — sitio público de
solo lectura). `storefront_contenido` es el CMS mínimo del sitio de marca
(`clave` fija validada en `application/contenido.py`; ver `data-model.md`
§18). Las tres columnas nuevas son nullable y sin backfill: un producto,
un insumo o una sucursal sin descripción/teléfono siguen funcionando
exactamente igual que hoy en el PDV y en el resto del ERP.

Revision ID: 405c9227fce3
Revises: d518f6efa2ce
Create Date: 2026-09-17 00:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "405c9227fce3"
down_revision: str | None = "d518f6efa2ce"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "storefront_contenido",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("marca_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("clave", sa.String(length=40), nullable=False),
        sa.Column(
            "valor", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "clave IN ('hero', 'nosotros', 'contacto', 'trabaja', 'pie', 'seo')",
            name="clave_storefront_contenido",
        ),
        sa.ForeignKeyConstraint(["marca_id"], ["marca.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("marca_id", "clave"),
    )
    op.create_index(
        op.f("ix_storefront_contenido_marca_id"), "storefront_contenido", ["marca_id"],
        unique=False,
    )

    op.add_column("producto_comercial", sa.Column("descripcion", sa.Text(), nullable=True))
    op.add_column("articulo", sa.Column("descripcion", sa.Text(), nullable=True))
    op.add_column("sucursal", sa.Column("telefono", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("sucursal", "telefono")
    op.drop_column("articulo", "descripcion")
    op.drop_column("producto_comercial", "descripcion")

    op.drop_index(op.f("ix_storefront_contenido_marca_id"), table_name="storefront_contenido")
    op.drop_table("storefront_contenido")
