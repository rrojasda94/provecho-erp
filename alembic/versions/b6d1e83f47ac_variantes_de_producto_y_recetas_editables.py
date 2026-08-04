"""variantes de producto, grupos de opciones y expresión en la receta

Tres cambios de un mismo slice (ADR-023):

1. **Variantes** (`producto_comercial.producto_padre_id` + `orden`): "Pizza
   Peperoni Personal/Mediana/Familiar" son productos hijos con receta y
   precio propios, no un recargo sobre un precio base. Por eso
   `receta_id` pasa a ser nullable: el padre agrupa, no se prepara ni se
   vende (RN-COM-022).
2. **Grupos de opciones** (`producto_opcion_grupo` +
   `producto_comercial_extra.grupo_id`): qué extras van juntos y cuántos
   hay que elegir. `minimo >= 1` vuelve el grupo obligatorio (RN-COM-023);
   no hay columna `obligatorio` porque sería el mismo dato dos veces.
3. **`receta_item.expresion`**: lo que el usuario tecleó cuando la cantidad
   salió de una operación ("1000/3"). Se guarda para poder reeditarla; la
   verdad sigue siendo `cantidad`, ya redondeada a los decimales de la UdM.

Nada de lo ya cargado cambia de comportamiento: todo producto existente
queda sin padre (producto simple) y todo extra queda sin grupo (opcional).

Revision ID: b6d1e83f47ac
Revises: 1805c0904c5c
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b6d1e83f47ac"
down_revision = "1805c0904c5c"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    # --- 1. Variantes -------------------------------------------------------
    op.add_column(
        "producto_comercial",
        sa.Column("producto_padre_id", UUID, nullable=True),
    )
    op.add_column(
        "producto_comercial",
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_producto_comercial_padre",
        "producto_comercial",
        "producto_comercial",
        ["producto_padre_id"],
        ["id"],
    )
    op.create_index(
        "ix_producto_comercial_padre",
        "producto_comercial",
        ["producto_padre_id"],
    )
    op.alter_column("producto_comercial", "receta_id", nullable=True)

    # --- 2. Grupos de opciones ---------------------------------------------
    op.create_table(
        "producto_opcion_grupo",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "producto_comercial_id",
            UUID,
            sa.ForeignKey("producto_comercial.id"),
            nullable=False,
        ),
        sa.Column("nombre", sa.String(50), nullable=False),
        sa.Column("minimo", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("maximo", sa.Integer(), nullable=True),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint("producto_comercial_id", "nombre", name="uq_producto_grupo"),
    )
    op.add_column(
        "producto_comercial_extra",
        sa.Column("grupo_id", UUID, nullable=True),
    )
    op.create_foreign_key(
        "fk_producto_extra_grupo",
        "producto_comercial_extra",
        "producto_opcion_grupo",
        ["grupo_id"],
        ["id"],
    )

    # --- 3. Expresión de la línea de receta ---------------------------------
    op.add_column("receta_item", sa.Column("expresion", sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column("receta_item", "expresion")
    op.drop_constraint(
        "fk_producto_extra_grupo", "producto_comercial_extra", type_="foreignkey"
    )
    op.drop_column("producto_comercial_extra", "grupo_id")
    op.drop_table("producto_opcion_grupo")
    # `receta_id` vuelve a NOT NULL: si quedó algún producto con variantes,
    # bajar la migración lo dejaría sin receta y la venta fallaría. Se
    # borran primero las variantes, que en este esquema no tienen sentido.
    op.execute("DELETE FROM producto_comercial WHERE producto_padre_id IS NOT NULL")
    op.drop_index("ix_producto_comercial_padre", table_name="producto_comercial")
    op.drop_constraint(
        "fk_producto_comercial_padre", "producto_comercial", type_="foreignkey"
    )
    op.drop_column("producto_comercial", "orden")
    op.drop_column("producto_comercial", "producto_padre_id")
    op.alter_column("producto_comercial", "receta_id", nullable=False)
