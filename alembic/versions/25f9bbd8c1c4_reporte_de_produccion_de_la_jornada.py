"""reporte de produccion de la jornada

Bloque `feat/produccion-reporte-de-jornada` del plan de deuda de
producción (RN-DOC-010). Tabla nueva, aditiva: `reporte_produccion`
consolida las órdenes que cerraron control de calidad en un almacén un
día dado (`ordenes` JSONB, snapshot al generar — no una vista en vivo),
con `merma_total`, `desperdicio_total`, `horas_hombre_total` y
`costo_total` agregados. Única por `(almacen_id, jornada)`:
`application/reportes_jornada.py::generar_reporte_jornada` recalcula el
existente mientras no esté visado (`visado_por`/`visado_at` nullable) y
deja de tocarlo en cuanto lo está — "se visa, no se redacta".

También agrega `orden_produccion.completado_at` (nullable): la columna
que dice cuándo cerró control de calidad la orden, para poder agruparlas
por jornada — `updated_at` no sirve porque cualquier `flush` (p. ej.
`registrar_consumo`) lo pisa antes de que la orden llegue a cerrarse.

Revision ID: 25f9bbd8c1c4
Revises: 9e6de2fa3a5d
Create Date: 2026-09-09 19:17:43.437671

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '25f9bbd8c1c4'
down_revision: str | None = '9e6de2fa3a5d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'reporte_produccion',
        sa.Column('almacen_id', sa.Uuid(), nullable=False),
        sa.Column('jornada', sa.Date(), nullable=False),
        sa.Column(
            'generado_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'ordenes',
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
            nullable=False,
        ),
        sa.Column('merma_total', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('desperdicio_total', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('horas_hombre_total', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('costo_total', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('visado_por', sa.Uuid(), nullable=True),
        sa.Column('visado_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('observaciones', sa.String(length=1000), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['almacen_id'], ['almacen.id'],
            name=op.f('fk_reporte_produccion_almacen_id_almacen'),
        ),
        sa.ForeignKeyConstraint(
            ['visado_por'], ['usuario.id'],
            name=op.f('fk_reporte_produccion_visado_por_usuario'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_reporte_produccion')),
        sa.UniqueConstraint(
            'almacen_id', 'jornada', name=op.f('uq_reporte_produccion_almacen_id'),
        ),
    )
    op.add_column(
        'orden_produccion', sa.Column('completado_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('orden_produccion', 'completado_at')
    op.drop_table('reporte_produccion')
