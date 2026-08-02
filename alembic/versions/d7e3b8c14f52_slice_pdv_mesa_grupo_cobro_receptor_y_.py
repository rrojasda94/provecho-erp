"""slice pdv: mesa, grupo de cobro, receptor de comprobante y descuento de orden

Cierra los huecos que el punto de venta necesitaba y el modelo no daba
(ADR-018):

- `mesa`: el salón deja de vivir en el texto libre de
  `venta.referencia_atencion` y pasa a ser un dato tipado por sucursal.
- `grupo_cobro` en `venta_item`, `pago` y `comprobante`: una venta puede
  dividirse entre varios pagadores, cada cuenta con su propio comprobante.
- `comprobante.receptor_num_doc` / `receptor_nombre`: el DNI o RUC que el
  cajero teclea al cobrar, sin exigir cliente registrado.
- descuento manual de orden en `venta`, con motivo y autorizador.

Todo lo agregado es nullable o trae `server_default`, de modo que las filas
existentes quedan válidas sin backfill. `grupo_cobro` nace en 1: una venta
anterior a este cambio es una venta con una sola cuenta.

Revision ID: d7e3b8c14f52
Revises: c9a2f4e18b60
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d7e3b8c14f52"
down_revision = "c9a2f4e18b60"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "mesa",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("sucursal_id", UUID, sa.ForeignKey("sucursal.id"), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("zona", sa.String(length=50), nullable=True),
        sa.Column("capacidad", sa.Integer(), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("sucursal_id", "numero", name="uq_mesa_sucursal_numero"),
    )
    op.create_index("ix_mesa_sucursal_id", "mesa", ["sucursal_id"])

    # --- venta: mesa, comensales y descuento manual --------------------------
    op.add_column("venta", sa.Column("mesa_id", UUID, nullable=True))
    op.create_foreign_key(
        "fk_venta_mesa", "venta", "mesa", ["mesa_id"], ["id"]
    )
    op.add_column("venta", sa.Column("comensales", sa.Integer(), nullable=True))
    op.add_column(
        "venta",
        sa.Column(
            "descuento_modo",
            sa.Enum(
                "porcentaje", "monto", name="modo_descuento_venta", native_enum=False
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "venta", sa.Column("descuento_valor", sa.Numeric(10, 2), nullable=True)
    )
    op.add_column(
        "venta", sa.Column("descuento_motivo", sa.String(length=60), nullable=True)
    )
    op.add_column(
        "venta", sa.Column("descuento_autorizado_por", UUID, nullable=True)
    )
    op.create_foreign_key(
        "fk_venta_descuento_autorizado_por",
        "venta",
        "usuario",
        ["descuento_autorizado_por"],
        ["id"],
    )

    # --- grupo de cobro ------------------------------------------------------
    for tabla in ("venta_item", "pago", "comprobante"):
        op.add_column(
            tabla,
            sa.Column(
                "grupo_cobro",
                sa.Integer(),
                nullable=False,
                server_default="1",
            ),
        )
    op.create_index(
        "ix_comprobante_venta_grupo", "comprobante", ["venta_id", "grupo_cobro"]
    )

    # --- receptor tecleado en caja -------------------------------------------
    op.add_column(
        "comprobante",
        sa.Column("receptor_num_doc", sa.String(length=11), nullable=True),
    )
    op.add_column(
        "comprobante",
        sa.Column("receptor_nombre", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("comprobante", "receptor_nombre")
    op.drop_column("comprobante", "receptor_num_doc")
    op.drop_index("ix_comprobante_venta_grupo", table_name="comprobante")
    for tabla in ("comprobante", "pago", "venta_item"):
        op.drop_column(tabla, "grupo_cobro")

    op.drop_constraint("fk_venta_descuento_autorizado_por", "venta", type_="foreignkey")
    op.drop_column("venta", "descuento_autorizado_por")
    op.drop_column("venta", "descuento_motivo")
    op.drop_column("venta", "descuento_valor")
    op.drop_column("venta", "descuento_modo")
    op.drop_column("venta", "comensales")
    op.drop_constraint("fk_venta_mesa", "venta", type_="foreignkey")
    op.drop_column("venta", "mesa_id")

    op.drop_index("ix_mesa_sucursal_id", table_name="mesa")
    op.drop_table("mesa")
