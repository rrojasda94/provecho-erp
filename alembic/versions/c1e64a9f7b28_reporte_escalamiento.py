"""reporte de escalamiento: la cadena supervisor - comercial - gerencia

Revision ID: c1e64a9f7b28
Revises: b8d3f47c1e59
Create Date: 2026-08-09 10:30:00.000000

RN-CTP-004 y RN-PRD-014 exigen desde el principio que un problema que no se
resuelve en su nivel se eleve y quede registrado. Estaba diseñado en
`data-model.md` y declarado como deuda en ADR-033; esta tabla lo salda.

Ancla a `reporte_emitido` y no a la venta: `referencia_tipo` + `referencia_id`
ya resuelven a qué apunta el hecho, para los nueve tipos y no para tres
(ADR-036). `ondelete=RESTRICT` porque el reporte es la evidencia de la cadena.

Índice parcial en vez de `UniqueConstraint` para "una cadena abierta por
reporte": las cerradas tienen que poder convivir, y dos UNIQUE que empiezan
por la misma columna colisionan de nombre con la convención de
`core/database.py` (el bug de `guia_remision`, CHANGELOG 2026-08-06).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'c1e64a9f7b28'
down_revision: str | None = 'b8d3f47c1e59'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        'reporte_escalamiento',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column('sucursal_id', sa.Uuid(), nullable=True),
        sa.Column('reporte_emitido_id', sa.Uuid(), nullable=False),
        sa.Column(
            'origen',
            sa.Enum(
                'central_pedidos',
                'punto_venta',
                'produccion',
                name='origen_escalamiento',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            'motivo',
            sa.Enum(
                'queja',
                'demora',
                'error_sistema',
                'desistimiento_no_resuelto',
                'no_conformidad_calidad',
                name='motivo_escalamiento',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('descripcion', sa.Text(), nullable=False),
        sa.Column('reportado_por_id', sa.Uuid(), nullable=False),
        sa.Column('evidencia_id', sa.Uuid(), nullable=True),
        sa.Column(
            'nivel_actual',
            sa.Enum(
                'supervisor',
                'comercial',
                'gerencia',
                name='nivel_escalamiento',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            'estado',
            sa.Enum(
                'abierto',
                'resuelto_supervisor',
                'escalado',
                'resuelto',
                'cerrado',
                name='estado_escalamiento',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            'acciones',
            sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'),
            nullable=False,
        ),
        sa.Column('cerrado_at', sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "(estado NOT IN ('resuelto_supervisor', 'resuelto', 'cerrado')) "
            "OR (cerrado_at IS NOT NULL)",
            name='ck_reporte_escalamiento_cierre_fechado',
        ),
        sa.ForeignKeyConstraint(
            ['empresa_id'],
            ['empresa.id'],
            name='fk_reporte_escalamiento_empresa_id_empresa',
        ),
        sa.ForeignKeyConstraint(
            ['sucursal_id'],
            ['sucursal.id'],
            name='fk_reporte_escalamiento_sucursal_id_sucursal',
        ),
        sa.ForeignKeyConstraint(
            ['reporte_emitido_id'],
            ['reporte_emitido.id'],
            name='fk_reporte_escalamiento_reporte_emitido_id_reporte_emitido',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['reportado_por_id'],
            ['usuario.id'],
            name='fk_reporte_escalamiento_reportado_por_id_usuario',
        ),
        sa.ForeignKeyConstraint(
            ['evidencia_id'],
            ['archivo.id'],
            name='fk_reporte_escalamiento_evidencia_id_archivo',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_reporte_escalamiento'),
    )
    op.create_index(
        'ix_reporte_escalamiento_reporte_emitido_id',
        'reporte_escalamiento',
        ['reporte_emitido_id'],
    )
    op.create_index(
        'uq_escalamiento_abierto_por_reporte',
        'reporte_escalamiento',
        ['reporte_emitido_id'],
        unique=True,
        sqlite_where=sa.text(
            "estado NOT IN ('resuelto_supervisor', 'resuelto', 'cerrado')"
        ),
        postgresql_where=sa.text(
            "estado NOT IN ('resuelto_supervisor', 'resuelto', 'cerrado')"
        ),
    )
    op.create_index(
        'ix_reporte_escalamiento_pendientes',
        'reporte_escalamiento',
        ['empresa_id', 'nivel_actual', 'estado'],
    )
    op.create_index(
        'ix_reporte_escalamiento_empresa',
        'reporte_escalamiento',
        ['empresa_id', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_reporte_escalamiento_empresa', 'reporte_escalamiento')
    op.drop_index('ix_reporte_escalamiento_pendientes', 'reporte_escalamiento')
    op.drop_index('uq_escalamiento_abierto_por_reporte', 'reporte_escalamiento')
    op.drop_index(
        'ix_reporte_escalamiento_reporte_emitido_id', 'reporte_escalamiento'
    )
    op.drop_table('reporte_escalamiento')
