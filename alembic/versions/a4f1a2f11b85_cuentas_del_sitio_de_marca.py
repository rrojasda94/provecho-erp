"""cuentas del sitio de marca: cuenta, direccion, favorito, refresh_token

Segundo slice de `storefront` (ADR-104, PR2): la cuenta de cliente web es
una credencial completamente aparte de `usuario` — su propio secreto de
JWT y su propia tabla de refresh token, con la misma mecánica de rotación
que `refresh_token` del ERP pero sin compartir fila.

Escrita a mano (sin Postgres disponible en este entorno para
`alembic --autogenerate`; revisar con `alembic check` antes de mergear).

Revision ID: a4f1a2f11b85
Revises: 405c9227fce3
Create Date: 2026-09-17 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str = "a4f1a2f11b85"
down_revision: str | None = "405c9227fce3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "storefront_cuenta",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("google_sub", sa.String(length=255), nullable=True),
        sa.Column("nombres", sa.String(length=150), nullable=False),
        sa.Column("apellidos", sa.String(length=150), nullable=False),
        sa.Column("tipo_documento", sa.String(length=10), nullable=True),
        sa.Column("numero_documento", sa.String(length=15), nullable=True),
        sa.Column("telefono", sa.String(length=20), nullable=True),
        sa.Column("fecha_nacimiento", sa.Date(), nullable=True),
        sa.Column("cliente_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("intentos_fallidos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("bloqueado_hasta", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["cliente_id"], ["cliente.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("google_sub"),
        sa.UniqueConstraint("cliente_id"),
    )
    op.create_index(
        op.f("ix_storefront_cuenta_email"), "storefront_cuenta", ["email"], unique=True,
    )

    op.create_table(
        "storefront_direccion",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("cuenta_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("etiqueta", sa.String(length=50), nullable=True),
        sa.Column("direccion", sa.String(length=255), nullable=False),
        sa.Column("referencia", sa.String(length=255), nullable=True),
        sa.Column("predeterminada", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ubicacion_place_id", sa.String(length=255), nullable=True),
        sa.Column("ubicacion_lat", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("ubicacion_lng", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("ubicacion_plus_code", sa.String(length=20), nullable=True),
        sa.Column("ubicacion_distrito", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["cuenta_id"], ["storefront_cuenta.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_storefront_direccion_cuenta_id"), "storefront_direccion", ["cuenta_id"],
        unique=False,
    )

    op.create_table(
        "storefront_favorito",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("cuenta_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("producto_comercial_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["cuenta_id"], ["storefront_cuenta.id"]),
        sa.ForeignKeyConstraint(["producto_comercial_id"], ["producto_comercial.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cuenta_id", "producto_comercial_id"),
    )
    op.create_index(
        op.f("ix_storefront_favorito_cuenta_id"), "storefront_favorito", ["cuenta_id"],
        unique=False,
    )

    op.create_table(
        "storefront_refresh_token",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("cuenta_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("sesion_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revocado", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["cuenta_id"], ["storefront_cuenta.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_storefront_refresh_token_cuenta_id"), "storefront_refresh_token",
        ["cuenta_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_storefront_refresh_token_cuenta_id"), table_name="storefront_refresh_token",
    )
    op.drop_table("storefront_refresh_token")

    op.drop_index(op.f("ix_storefront_favorito_cuenta_id"), table_name="storefront_favorito")
    op.drop_table("storefront_favorito")

    op.drop_index(
        op.f("ix_storefront_direccion_cuenta_id"), table_name="storefront_direccion",
    )
    op.drop_table("storefront_direccion")

    op.drop_index(op.f("ix_storefront_cuenta_email"), table_name="storefront_cuenta")
    op.drop_table("storefront_cuenta")
