"""pedidos del sitio de marca y canal web: storefront_pedido,
storefront_pedido_item, canal 'web' en venta/lista_precio

Tercer slice de `storefront` (ADR-105, PR3): carrito, checkout
(invitado o con cuenta), asignación automática de local, ETA y pago en
efectivo o Izipay. `venta.canal`/`lista_precio.canal` ganan el valor `web`
que faltaba desde PR1 (`sales.domain.rules.CANALES`).

Escrita a mano (sin Postgres disponible en este entorno para
`alembic --autogenerate`; revisar con `alembic check` antes de mergear).

Revision ID: 3070159f64bd
Revises: a4f1a2f11b85
Create Date: 2026-09-17 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str = "3070159f64bd"
down_revision: str | None = "a4f1a2f11b85"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("canal_venta", "venta", type_="check")
    op.create_check_constraint(
        "canal_venta", "venta", sa.text("canal IN ('pdv', 'agente_ia', 'delivery', 'web')")
    )
    op.drop_constraint("canal_lista_precio", "lista_precio", type_="check")
    op.create_check_constraint(
        "canal_lista_precio",
        "lista_precio",
        sa.text("canal IN ('pdv', 'agente_ia', 'delivery', 'web')"),
    )

    op.create_table(
        "storefront_pedido",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("marca_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("cuenta_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("nombre_contacto", sa.String(length=150), nullable=False),
        sa.Column("telefono_contacto", sa.String(length=20), nullable=False),
        sa.Column("email_contacto", sa.String(length=255), nullable=True),
        sa.Column("modalidad", sa.String(length=10), nullable=False),
        sa.Column("sucursal_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("direccion_entrega", sa.String(length=255), nullable=True),
        sa.Column("ubicacion_place_id", sa.String(length=255), nullable=True),
        sa.Column("ubicacion_lat", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("ubicacion_lng", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("ubicacion_plus_code", sa.String(length=20), nullable=True),
        sa.Column("ubicacion_distrito", sa.String(length=100), nullable=True),
        sa.Column("medio_pago", sa.String(length=10), nullable=False),
        sa.Column("numero_documento", sa.String(length=15), nullable=True),
        sa.Column("nombre_o_razon_social", sa.String(length=150), nullable=True),
        sa.Column("total_estimado", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("costo_delivery_estimado", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("distancia_km_estimada", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("eta_min", sa.Integer(), nullable=True),
        sa.Column("eta_max", sa.Integer(), nullable=True),
        sa.Column(
            "estado", sa.String(length=12), server_default=sa.text("'pendiente'"), nullable=False
        ),
        sa.Column("fallo_motivo", sa.String(length=255), nullable=True),
        sa.Column("venta_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("numero_orden", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("token_acceso", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "modalidad IN ('takeout', 'delivery')", name="modalidad_storefront_pedido"
        ),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'confirmado', 'fallido')",
            name="estado_storefront_pedido",
        ),
        sa.CheckConstraint(
            "medio_pago IN ('efectivo', 'izipay')", name="medio_pago_storefront_pedido"
        ),
        sa.ForeignKeyConstraint(["marca_id"], ["marca.id"]),
        sa.ForeignKeyConstraint(["cuenta_id"], ["storefront_cuenta.id"]),
        sa.ForeignKeyConstraint(["sucursal_id"], ["sucursal.id"]),
        sa.ForeignKeyConstraint(["venta_id"], ["venta.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("venta_id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("token_acceso"),
    )
    op.create_index(
        op.f("ix_storefront_pedido_cuenta_id"), "storefront_pedido", ["cuenta_id"],
        unique=False,
    )

    op.create_table(
        "storefront_pedido_item",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("pedido_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("producto_comercial_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("nombre_congelado", sa.String(length=150), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unitario_congelado", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["pedido_id"], ["storefront_pedido.id"]),
        sa.ForeignKeyConstraint(["producto_comercial_id"], ["producto_comercial.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_storefront_pedido_item_pedido_id"), "storefront_pedido_item", ["pedido_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_storefront_pedido_item_pedido_id"), table_name="storefront_pedido_item",
    )
    op.drop_table("storefront_pedido_item")

    op.drop_index(op.f("ix_storefront_pedido_cuenta_id"), table_name="storefront_pedido")
    op.drop_table("storefront_pedido")

    op.drop_constraint("canal_lista_precio", "lista_precio", type_="check")
    op.create_check_constraint(
        "canal_lista_precio", "lista_precio", sa.text("canal IN ('pdv', 'agente_ia', 'delivery')")
    )
    op.drop_constraint("canal_venta", "venta", type_="check")
    op.create_check_constraint(
        "canal_venta", "venta", sa.text("canal IN ('pdv', 'agente_ia', 'delivery')")
    )
