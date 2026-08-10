"""reporte emitido: quien lo provoco y en que almacen

Revision ID: b8d3f47c1e59
Revises: a4f1d0c8b573
Create Date: 2026-08-09 10:00:00.000000

Un reporte decía qué pasó y no quién lo provocó ni dónde exactamente. Sin
eso, «ajuste de inventario fuera de margen» obliga a abrir el ERP en otra
pestaña para averiguar a quién preguntarle.

`almacen_id` ya lo resolvía `emision._ubicar()` para elegir destinatarios y
lo descartaba al persistir. `actor_id` es nuevo y sale de `Emision.clave_actor`.

**Sin backfill, y las dos columnas nullable.** Un reporte de agosto no puede
decir quién lo provocó porque el dato nunca se guardó: dirá «Sistema», que es
lo que dicen también los hechos que detecta un barrido (RN-REP-009).
Inventarle un actor a una fila vieja sería peor que dejarla sin él.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b8d3f47c1e59'
down_revision: str | None = 'a4f1d0c8b573'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'reporte_emitido', sa.Column('almacen_id', sa.Uuid(), nullable=True)
    )
    op.add_column(
        'reporte_emitido', sa.Column('actor_id', sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        'fk_reporte_emitido_almacen_id_almacen',
        'reporte_emitido',
        'almacen',
        ['almacen_id'],
        ['id'],
    )
    op.create_foreign_key(
        'fk_reporte_emitido_actor_id_usuario',
        'reporte_emitido',
        'usuario',
        ['actor_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_reporte_emitido_actor_id_usuario', 'reporte_emitido', type_='foreignkey'
    )
    op.drop_constraint(
        'fk_reporte_emitido_almacen_id_almacen', 'reporte_emitido', type_='foreignkey'
    )
    op.drop_column('reporte_emitido', 'actor_id')
    op.drop_column('reporte_emitido', 'almacen_id')
