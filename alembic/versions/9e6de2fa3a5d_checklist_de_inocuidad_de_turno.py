"""checklist de inocuidad de turno

Bloque `feat/produccion-checklist-inocuidad` del plan de deuda de
producción (RN-CDP-002/005). Tabla nueva, aditiva: `checklist_inocuidad_
turno` registra bioseguridad, superficies, limpieza intermedia, equipos de
frío (JSONB `[{equipo, temperatura_c, rango_min, rango_max, dentro_rango}]`,
`dentro_rango` calculado por el servidor) y posible indicio de plaga, con
`estado` (`aprobado`|`bloqueado`) calculado por `application/inocuidad.py`
— nunca lo decide quien lo registra.

Única por `(almacen_id, fecha, turno)`: un solo checklist por turno del
mismo almacén el mismo día. `turno` es texto libre, mismo criterio que
`plan_produccion.turno` (bloque `feat/produccion-plan-de-produccion`): una
cocina de producción central no siempre tiene sucursal, así que no hay FK a
`turno_sucursal` (RRHH).

Sin checklist `aprobado` vigente del día en el almacén, `crear_orden_
produccion` y `registrar_consumo` rechazan con 409 `cocina_bloqueada`
(RN-CDP-005) para almacenes `tipo=produccion`.

Revision ID: 9e6de2fa3a5d
Revises: 34d7a8d2cb46
Create Date: 2026-09-09 18:33:06.262989

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '9e6de2fa3a5d'
down_revision: str | None = '34d7a8d2cb46'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'checklist_inocuidad_turno',
        sa.Column('almacen_id', sa.Uuid(), nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('turno', sa.String(length=30), nullable=False),
        sa.Column('verificado_por', sa.Uuid(), nullable=False),
        sa.Column('bioseguridad_ok', sa.Boolean(), nullable=False),
        sa.Column('superficies_ok', sa.Boolean(), nullable=False),
        sa.Column('limpieza_intermedia_ok', sa.Boolean(), nullable=False),
        sa.Column(
            'equipos_frio',
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
            nullable=False,
        ),
        sa.Column('plaga_indicio', sa.Boolean(), nullable=False),
        sa.Column(
            'estado',
            sa.Enum(
                'aprobado', 'bloqueado',
                name='estado_checklist_inocuidad_turno', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint(
            "estado IN ('aprobado', 'bloqueado')",
            name=op.f('ck_checklist_inocuidad_turno_estado_checklist_inocuidad_turno'),
        ),
        sa.ForeignKeyConstraint(
            ['almacen_id'], ['almacen.id'],
            name=op.f('fk_checklist_inocuidad_turno_almacen_id_almacen'),
        ),
        sa.ForeignKeyConstraint(
            ['verificado_por'], ['usuario.id'],
            name=op.f('fk_checklist_inocuidad_turno_verificado_por_usuario'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_checklist_inocuidad_turno')),
        sa.UniqueConstraint(
            'almacen_id', 'fecha', 'turno',
            name=op.f('uq_checklist_inocuidad_turno_almacen_id'),
        ),
    )


def downgrade() -> None:
    op.drop_table('checklist_inocuidad_turno')
