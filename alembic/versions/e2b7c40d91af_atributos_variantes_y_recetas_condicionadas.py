"""atributos, variantes y recetas condicionadas

El catalogo modelaba la variante como producto hijo (ADR-023) y el sabor como
grupo de opciones de una sola eleccion (ADR-035). Cada combinacion vendible
necesitaba su propia fila de producto Y su propia receta. Con los datos reales
de Charlie's eso no se sostiene: una pizza mitad-y-mitad de 19 sabores por
mitad son 361 combinaciones, y en Odoo son UNA receta con 26 lineas
condicionadas.

Entran las seis tablas de atributos y variantes de Odoo, mas la condicion y la
unidad propia en la linea de receta, mas la jerarquia de categorias.

TODO ADITIVO, a proposito. Ninguna columna existente cambia de tipo ni de
nulabilidad, y todo lo nuevo nace NULL o con default. Con el interruptor
`sales`/`catalogo.modelo_odoo` apagado el comportamiento es identico al de
0.6.0, y la imagen 0.6.0 corre contra este esquema sin enterarse: esa es la
vuelta atras, y por eso no hace falta downgrade para volver a operar.

`receta_item.unidad_medida_id` no revierte lo que ADR-023 descarto. Lo
descartado era una unidad libre -dos verdades sobre la misma cantidad-. Esta
es de la misma categoria de UdM que la del articulo, que RN-UDM-001 siempre
admitio, y `unidad_medida.ratio` la convierte sin ambiguedad.

Las FK van declaradas dentro de la columna, sin nombre explicito, para que las
nombre la convencion de `src/core/database.py` -que es la que usa el modelo-.
Tres de ellas pasan los 63 caracteres de Postgres y las trunca SQLAlchemy con
su propio algoritmo; nombrarlas a mano aca daria un nombre distinto al del
modelo y `alembic check` marcaria deriva. Ya hay precedente:
`fk_producto_comercial_extra_producto_comercial_id_producto_comercial`.

Revision ID: e2b7c40d91af
Revises: d41f6a2c98b7
Create Date: 2026-08-23

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e2b7c40d91af"
down_revision: str | None = "d41f6a2c98b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = sa.Uuid(as_uuid=True)
JSONB = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
)


def _marcas_de_tiempo() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def upgrade() -> None:
    # --- 1. Atributos y sus valores ----------------------------------------
    op.create_table(
        "atributo",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("empresa_id", UUID, sa.ForeignKey("empresa.id"), nullable=False),
        sa.Column("nombre", sa.String(80), nullable=False),
        sa.Column(
            "modo_variante", sa.String(10), nullable=False, server_default="nunca"
        ),
        sa.Column("display", sa.String(10), nullable=False, server_default="radio"),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ref_externa", sa.String(120), nullable=True),
        *_marcas_de_tiempo(),
        sa.UniqueConstraint("empresa_id", "nombre", name="uq_atributo_empresa_nombre"),
        sa.UniqueConstraint("ref_externa", name="uq_atributo_ref_externa"),
    )
    op.create_index("ix_atributo_empresa_id", "atributo", ["empresa_id"])

    op.create_table(
        "atributo_valor",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("atributo_id", UUID, sa.ForeignKey("atributo.id"), nullable=False),
        sa.Column("nombre", sa.String(80), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "activo", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        *_marcas_de_tiempo(),
        sa.UniqueConstraint("atributo_id", "nombre", name="uq_atributo_valor_nombre"),
    )
    op.create_index("ix_atributo_valor_atributo_id", "atributo_valor", ["atributo_id"])

    # --- 2. Que ofrece cada producto ---------------------------------------
    op.create_table(
        "producto_atributo_linea",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "producto_comercial_id",
            UUID,
            sa.ForeignKey("producto_comercial.id"),
            nullable=False,
        ),
        sa.Column("atributo_id", UUID, sa.ForeignKey("atributo.id"), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        *_marcas_de_tiempo(),
        sa.UniqueConstraint(
            "producto_comercial_id", "atributo_id", name="uq_producto_atributo_linea"
        ),
    )
    op.create_index(
        "ix_producto_atributo_linea_producto_comercial_id",
        "producto_atributo_linea",
        ["producto_comercial_id"],
    )

    op.create_table(
        "producto_atributo_valor",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "linea_id",
            UUID,
            sa.ForeignKey("producto_atributo_linea.id"),
            nullable=False,
        ),
        sa.Column(
            "atributo_valor_id",
            UUID,
            sa.ForeignKey("atributo_valor.id"),
            nullable=False,
        ),
        sa.Column(
            "precio_extra", sa.Numeric(12, 2), nullable=False, server_default="0"
        ),
        sa.Column(
            "activo", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        *_marcas_de_tiempo(),
        sa.UniqueConstraint(
            "linea_id", "atributo_valor_id", name="uq_producto_atributo_valor"
        ),
    )
    op.create_index(
        "ix_producto_atributo_valor_linea_id", "producto_atributo_valor", ["linea_id"]
    )

    # --- 3. Que combinacion ES cada variante -------------------------------
    op.create_table(
        "producto_variante_valor",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "producto_comercial_id",
            UUID,
            sa.ForeignKey("producto_comercial.id"),
            nullable=False,
        ),
        sa.Column(
            "producto_atributo_valor_id",
            UUID,
            sa.ForeignKey("producto_atributo_valor.id"),
            nullable=False,
        ),
        *_marcas_de_tiempo(),
        sa.UniqueConstraint(
            "producto_comercial_id",
            "producto_atributo_valor_id",
            name="uq_producto_variante_valor",
        ),
    )
    op.create_index(
        "ix_producto_variante_valor_producto_comercial_id",
        "producto_variante_valor",
        ["producto_comercial_id"],
    )
    op.create_index(
        "ix_producto_variante_valor_producto_atributo_valor_id",
        "producto_variante_valor",
        ["producto_atributo_valor_id"],
    )

    # --- 4. Combinaciones que no existen -----------------------------------
    op.create_table(
        "producto_exclusion",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "producto_atributo_valor_id",
            UUID,
            sa.ForeignKey("producto_atributo_valor.id"),
            nullable=False,
        ),
        sa.Column(
            "excluye_valor_id",
            UUID,
            sa.ForeignKey("producto_atributo_valor.id"),
            nullable=False,
        ),
        *_marcas_de_tiempo(),
        sa.UniqueConstraint(
            "producto_atributo_valor_id",
            "excluye_valor_id",
            name="uq_producto_exclusion",
        ),
    )
    op.create_index(
        "ix_producto_exclusion_producto_atributo_valor_id",
        "producto_exclusion",
        ["producto_atributo_valor_id"],
    )

    # --- 5. Columnas sobre lo que ya existe. Nullable o con default. -------
    op.add_column(
        "producto_comercial", sa.Column("ref_externa", sa.String(120), nullable=True)
    )
    op.create_unique_constraint(
        "uq_producto_comercial_ref_externa", "producto_comercial", ["ref_externa"]
    )
    op.add_column("producto_comercial", sa.Column("lienzo_pos", JSONB, nullable=True))

    op.add_column(
        "venta_item", sa.Column("valores_variante_ids", JSONB, nullable=True)
    )

    op.add_column(
        "receta",
        sa.Column(
            "es_kit", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column("receta", sa.Column("ref_externa", sa.String(120), nullable=True))
    op.create_unique_constraint("uq_receta_ref_externa", "receta", ["ref_externa"])

    op.add_column("receta_item", sa.Column("unidad_medida_id", UUID, nullable=True))
    op.create_foreign_key(
        "fk_receta_item_unidad_medida_id_unidad_medida",
        "receta_item",
        "unidad_medida",
        ["unidad_medida_id"],
        ["id"],
    )
    op.add_column("receta_item", sa.Column("aplica_valores", JSONB, nullable=True))
    op.add_column(
        "receta_item",
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
    )

    op.add_column(
        "articulo", sa.Column("ref_externa", sa.String(120), nullable=True)
    )
    op.create_unique_constraint("uq_articulo_ref_externa", "articulo", ["ref_externa"])

    op.add_column("categoria", sa.Column("padre_id", UUID, nullable=True))
    op.create_foreign_key(
        "fk_categoria_padre_id_categoria",
        "categoria",
        "categoria",
        ["padre_id"],
        ["id"],
    )
    op.create_index("ix_categoria_padre_id", "categoria", ["padre_id"])


def downgrade() -> None:
    op.drop_index("ix_categoria_padre_id", table_name="categoria")
    op.drop_constraint(
        "fk_categoria_padre_id_categoria", "categoria", type_="foreignkey"
    )
    op.drop_column("categoria", "padre_id")

    op.drop_constraint("uq_articulo_ref_externa", "articulo", type_="unique")
    op.drop_column("articulo", "ref_externa")

    op.drop_column("receta_item", "orden")
    op.drop_column("receta_item", "aplica_valores")
    op.drop_constraint(
        "fk_receta_item_unidad_medida_id_unidad_medida",
        "receta_item",
        type_="foreignkey",
    )
    op.drop_column("receta_item", "unidad_medida_id")

    op.drop_constraint("uq_receta_ref_externa", "receta", type_="unique")
    op.drop_column("receta", "ref_externa")
    op.drop_column("receta", "es_kit")

    op.drop_column("venta_item", "valores_variante_ids")

    op.drop_column("producto_comercial", "lienzo_pos")
    op.drop_constraint(
        "uq_producto_comercial_ref_externa", "producto_comercial", type_="unique"
    )
    op.drop_column("producto_comercial", "ref_externa")

    op.drop_table("producto_exclusion")
    op.drop_table("producto_variante_valor")
    op.drop_table("producto_atributo_valor")
    op.drop_table("producto_atributo_linea")
    op.drop_table("atributo_valor")
    op.drop_table("atributo")
