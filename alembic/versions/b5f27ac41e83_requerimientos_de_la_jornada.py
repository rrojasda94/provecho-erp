"""requerimientos de la jornada

Revision ID: b5f27ac41e83
Revises: c8b41f60d2a7
Create Date: 2026-08-19 09:00:00.000000

Una sola columna: `solicitud_item.bajo_minimo_al_pedir`.

Es lo que separa la urgencia real del pedido del local (RN-INV-024). Se
estampa cuando el ítem entra a la lista y no se recalcula después: al momento
de aprobar, el stock ya se movió, y derivarlo entonces contaría una historia
distinta de la que el local vio al pedir. Las solicitudes anteriores quedan
en `false`, que es lo honesto: de ellas no se sabe si el SKU estaba bajo su
mínimo, y suponer que sí las marcaría a todas como urgentes.

**Sin cambio de esquema para el estado `borrador`** (RN-INV-023), aunque el
enum `estado_solicitud` gane un valor. Dos razones, las dos verificadas
contra el modelo y no supuestas:

- `Enum(..., native_enum=False)` en SQLAlchemy 2.x trae `create_constraint`
  en `False`, así que la columna es un VARCHAR pelado: no hay CHECK que
  dropear ni recrear.
- Ese VARCHAR es de largo 10 (lo fija `despachada`, el valor más largo) y
  `borrador` mide 8, así que entra sin ampliar nada. Es justo el tipo de
  detalle que SQLite no habría dejado ver: ahí el largo no se valida.
"""

import sqlalchemy as sa
from alembic import op

revision = "b5f27ac41e83"
down_revision = "c8b41f60d2a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "solicitud_item",
        sa.Column(
            "bajo_minimo_al_pedir",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    # Los borradores no sobreviven a la vuelta atrás: sin la columna siguen
    # siendo filas válidas, pero `borrador` deja de significar nada para el
    # código anterior y quedarían como solicitudes que nadie puede aprobar
    # ni cancelar. Se descartan, que es lo que son: listas sin enviar.
    op.execute("DELETE FROM solicitud_item WHERE solicitud_id IN "
               "(SELECT id FROM solicitud_insumos WHERE estado = 'borrador')")
    op.execute("DELETE FROM solicitud_insumos WHERE estado = 'borrador'")
    op.drop_column("solicitud_item", "bajo_minimo_al_pedir")
