"""Nombre público de insumos y atributos, y cuentas del sitio sin repetidos

Dos cosas que solo se notan en el sitio de marca:

1. `nombre_publico` en `articulo`, `atributo` y `atributo_valor`. El nombre
   interno está escrito para el almacén y para quien arma el catálogo ("QUESO
   EDAM BLOQUE 3KG", "Mitad 1 F") y el sitio lo mostraba tal cual al comensal.
   Renombrar el registro no sirve: el almacén necesita distinguir dos quesos
   que al cliente le dan igual. Son dos públicos, así que son dos nombres.
   Nullable: vacío significa "usa el de siempre", y nadie tiene que cargar
   nada para que todo siga como está.

2. DNI y teléfono únicos en `storefront_cuenta`. Solo el email lo era, así que
   la misma persona podía abrir varias cuentas con el mismo documento y
   terminar con los pedidos repartidos entre ellas.

   Índices **parciales** (`WHERE deleted_at IS NULL`): una cuenta dada de baja
   no puede seguir reservando un DNI. Y antes de crearlos se desactivan los
   repetidos que ya existan, conservando **la cuenta más antigua** de cada
   documento o teléfono — si no, esta migración tumbaría el despliegue en
   cualquier base con datos de prueba, que es exactamente donde está. El
   borrado es lógico (`deleted_at`), así que es reversible mirando la tabla.

Revision ID: b3c81d4e9a17
Revises: cec53f7b2f6e
Create Date: 2026-09-20 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str = "b3c81d4e9a17"
down_revision: str | None = "cec53f7b2f6e"
branch_labels = None
depends_on = None


#: (columna, nombre del índice). El orden importa: se desduplica y se indexa
#: campo por campo, y una cuenta puede repetir los dos.
CAMPOS_UNICOS = [
    ("numero_documento", "uq_storefront_cuenta_documento"),
    ("telefono", "uq_storefront_cuenta_telefono"),
]


def _desactivar_repetidas(campo: str) -> None:
    """Deja viva la más antigua de cada valor repetido; el resto, de baja.

    `EXISTS` contra la misma tabla y no un `GROUP BY` con `MIN(id)`: el id es
    un UUID y su mínimo es alfabético, o sea al azar. Lo que decide es
    `created_at`, con el id solo para desempatar dos cuentas creadas en el
    mismo instante.
    """
    op.execute(
        sa.text(
            f"""
            UPDATE storefront_cuenta
               SET deleted_at = CURRENT_TIMESTAMP
             WHERE deleted_at IS NULL
               AND {campo} IS NOT NULL
               AND EXISTS (
                   SELECT 1
                     FROM storefront_cuenta AS anterior
                    WHERE anterior.deleted_at IS NULL
                      AND anterior.{campo} = storefront_cuenta.{campo}
                      AND (
                          anterior.created_at < storefront_cuenta.created_at
                          OR (
                              anterior.created_at = storefront_cuenta.created_at
                              AND anterior.id < storefront_cuenta.id
                          )
                      )
               )
            """
        )
    )


def upgrade() -> None:
    for tabla in ("articulo", "atributo", "atributo_valor"):
        op.add_column(tabla, sa.Column("nombre_publico", sa.String(80), nullable=True))

    for campo, indice in CAMPOS_UNICOS:
        _desactivar_repetidas(campo)
        op.create_index(
            indice,
            "storefront_cuenta",
            [campo],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
            sqlite_where=sa.text("deleted_at IS NULL"),
        )


def downgrade() -> None:
    for _, indice in CAMPOS_UNICOS:
        op.drop_index(indice, table_name="storefront_cuenta")
    for tabla in ("articulo", "atributo", "atributo_valor"):
        op.drop_column(tabla, "nombre_publico")
