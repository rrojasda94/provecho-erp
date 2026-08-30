"""factura del proveedor y unicidad por direccion

La factura de un proveedor no se podía representar: `comprobante` guardaba
tipo, serie y correlativo y nada más. Faltaban la fecha del papel —el
`created_at` es cuándo lo tecleó alguien—, su importe —se tomaba
implícitamente de `orden_compra.total`, que es la base de lo recibido— y
quién lo emitió.

Y la unicidad estaba mal: `(empresa_id, serie, correlativo)` no distinguía
`direccion`, así que la primera factura F001-1 que entrara bloqueaba ese
número **en toda la empresa** — incluida nuestra propia serie F001, la que se
declara a SUNAT. Se parte en dos índices parciales: el emitido es único por
empresa; el recibido, por emisor.

Revision ID: 0a056863874b
Revises: 832ff01ed33f
Create Date: 2026-08-30

"""

import sqlalchemy as sa
from alembic import op

revision = "0a056863874b"
down_revision = "832ff01ed33f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "comprobante", sa.Column("emisor_num_doc", sa.String(length=11), nullable=True)
    )
    op.add_column("comprobante", sa.Column("fecha_emision", sa.Date(), nullable=True))
    op.add_column(
        "comprobante",
        sa.Column("total", sa.Numeric(precision=12, scale=2), nullable=True),
    )

    # El emisor de una factura de compra **es** el proveedor de su OC: eso sí
    # se puede derivar y hay que hacerlo, porque es la columna de la que
    # depende la unicidad nueva. Subconsulta correlacionada y no `UPDATE FROM`
    # para que corra igual en Postgres y en SQLite.
    op.execute(
        """
        UPDATE comprobante
           SET emisor_num_doc = (
               SELECT p.ruc
                 FROM orden_compra oc
                 JOIN proveedor p ON p.id = oc.proveedor_id
                WHERE oc.id = comprobante.compra_id
           )
         WHERE direccion = 'recibido' AND compra_id IS NOT NULL
        """
    )
    # `total` y `fecha_emision` quedan NULL a propósito en lo ya registrado.
    # `orden_compra.total` es la base valorizada de lo que se recibió, no lo
    # que la factura declara: difieren por IGV, detracción, redondeo y notas.
    # Copiarlo produciría un número que parece venir del papel y no viene, y
    # nadie podría distinguirlo después. La pantalla muestra el total de la OC
    # como dato aparte, que es honesto.

    op.drop_constraint(
        op.f("uq_comprobante_empresa_id"), "comprobante", type_="unique"
    )
    op.create_index(
        "uq_comprobante_emitido",
        "comprobante",
        ["empresa_id", "serie", "correlativo"],
        unique=True,
        postgresql_where=sa.text("direccion = 'emitido'"),
        sqlite_where=sa.text("direccion = 'emitido'"),
    )
    op.create_index(
        "uq_comprobante_recibido",
        "comprobante",
        ["empresa_id", "emisor_num_doc", "serie", "correlativo"],
        unique=True,
        postgresql_where=sa.text(
            "direccion = 'recibido' AND emisor_num_doc IS NOT NULL"
        ),
        sqlite_where=sa.text("direccion = 'recibido' AND emisor_num_doc IS NOT NULL"),
    )
    op.create_index("ix_comprobante_compra_id", "comprobante", ["compra_id"])


def downgrade() -> None:
    """Puede fallar con datos reales, y es información y no un defecto: si ya
    existen dos facturas de proveedores distintos con la misma serie y
    correlativo, la constraint global no se puede recrear. En CI el
    `downgrade base` corre sobre base vacía."""
    op.drop_index("ix_comprobante_compra_id", table_name="comprobante")
    op.drop_index("uq_comprobante_recibido", table_name="comprobante")
    op.drop_index("uq_comprobante_emitido", table_name="comprobante")
    op.create_unique_constraint(
        op.f("uq_comprobante_empresa_id"),
        "comprobante",
        ["empresa_id", "serie", "correlativo"],
    )
    op.drop_column("comprobante", "total")
    op.drop_column("comprobante", "fecha_emision")
    op.drop_column("comprobante", "emisor_num_doc")
