"""subrecetas anidadas orden padre

Bloque `feat/produccion-subrecetas-anidadas` del plan de deuda de
producción (RN-PRD-020). Agrega `orden_produccion.orden_padre_id`
(autorreferencia nullable, indexada): una orden hija fabrica una
subreceta que el consumo sugerido de su padre marcó `requiere_orden_
hija` — insumo con receta BOM propia y sin disponible suficiente en el
almacén. Sin tope de niveles (una subreceta puede colgar de otra) y sin
riesgo de ciclo: una fila nueva no puede referenciarse a sí misma al
crearse.

También amplía el `CheckConstraint` de `origen` con el valor nuevo
`subreceta_anidada` (autogenerate no compara el cuerpo de los `CHECK`,
así que se recrea a mano — mismo patrón ya visto en este módulo).

Revision ID: 74e3f09568a0
Revises: 25f9bbd8c1c4
Create Date: 2026-09-09 19:51:59.021138

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '74e3f09568a0'
down_revision: str | None = '25f9bbd8c1c4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('orden_produccion', sa.Column('orden_padre_id', sa.Uuid(), nullable=True))
    op.create_index(
        op.f('ix_orden_produccion_orden_padre_id'), 'orden_produccion', ['orden_padre_id'],
        unique=False,
    )
    op.create_foreign_key(
        op.f('fk_orden_produccion_orden_padre_id_orden_produccion'),
        'orden_produccion', 'orden_produccion', ['orden_padre_id'], ['id'],
    )
    op.drop_constraint('origen_orden_produccion', 'orden_produccion', type_='check')
    op.create_check_constraint(
        'origen_orden_produccion',
        'orden_produccion',
        "origen IN ('manual', 'ajuste_por_necesidad', 'plan', 'subreceta_anidada')",
    )


def downgrade() -> None:
    op.drop_constraint('origen_orden_produccion', 'orden_produccion', type_='check')
    op.create_check_constraint(
        'origen_orden_produccion',
        'orden_produccion',
        "origen IN ('manual', 'ajuste_por_necesidad', 'plan')",
    )
    op.drop_constraint(
        op.f('fk_orden_produccion_orden_padre_id_orden_produccion'), 'orden_produccion',
        type_='foreignkey',
    )
    op.drop_index(op.f('ix_orden_produccion_orden_padre_id'), table_name='orden_produccion')
    op.drop_column('orden_produccion', 'orden_padre_id')
