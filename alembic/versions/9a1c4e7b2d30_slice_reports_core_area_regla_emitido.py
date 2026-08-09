"""slice reports core: area, regla de distribucion, reporte emitido, entrega

Revision ID: 9a1c4e7b2d30
Revises: b3f7d21a9c04
Create Date: 2026-08-08 12:00:00.000000

El ERP publica 52 eventos y hasta ahora cuatro llegaban a una persona, con
los destinatarios cableados en dos funciones de Python. Estas seis tablas son
lo que hace administrable «quién recibe qué» (ADR-033).

`area` + `area_miembro` le dan cuerpo a los destinos que el ERP ya nombraba
sin poder resolver (`dirigido_a: [almacen, gerencia]`,
`devolucion.reporte_dirigido_a`). `regla_distribucion` +
`regla_destinatario` son el gobierno. `reporte_emitido` + `entrega_reporte`
son el rastro: qué se generó, a quién le tocó y por qué.

Dos índices parciales en vez de una `UniqueConstraint` de tres columnas para
la unicidad de la regla: en SQL los NULL son distintos entre sí, así que la
constraint simple dejaría convivir dos reglas generales de la misma emisión
y el hecho se entregaría dos veces (RN-REP-008).

El catálogo de emisiones **no es una tabla**: es una lista cerrada en
`src/modules/reports/domain/catalogo.py`. `codigo_emision` es texto validado
contra ella al guardar, no una FK.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '9a1c4e7b2d30'
down_revision: str | None = 'b3f7d21a9c04'
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
        'area',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column('codigo', sa.String(length=30), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('activa', sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('empresa_id', 'codigo', name='uq_area_empresa_codigo'),
    )
    op.create_index(op.f('ix_area_empresa_id'), 'area', ['empresa_id'], unique=False)

    op.create_table(
        'area_miembro',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('area_id', sa.Uuid(), nullable=False),
        sa.Column('rol_id', sa.Uuid(), nullable=True),
        sa.Column('usuario_id', sa.Uuid(), nullable=True),
        sa.Column('sucursal_id', sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            '(rol_id IS NULL) <> (usuario_id IS NULL)',
            name='ck_area_miembro_rol_o_usuario',
        ),
        sa.ForeignKeyConstraint(['area_id'], ['area.id']),
        sa.ForeignKeyConstraint(['rol_id'], ['rol.id']),
        sa.ForeignKeyConstraint(['sucursal_id'], ['sucursal.id']),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_area_miembro_area_id'), 'area_miembro', ['area_id'], unique=False
    )

    op.create_table(
        'regla_distribucion',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column('codigo_emision', sa.String(length=60), nullable=False),
        sa.Column('sucursal_id', sa.Uuid(), nullable=True),
        sa.Column('activa', sa.Boolean(), nullable=False),
        sa.Column(
            'nivel',
            sa.Enum('info', 'aviso', 'urgente', name='nivel_regla', native_enum=False),
            nullable=False,
        ),
        sa.Column(
            'canal',
            sa.Enum('bandeja', name='canal_regla', native_enum=False),
            nullable=False,
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id']),
        sa.ForeignKeyConstraint(['sucursal_id'], ['sucursal.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_regla_distribucion_empresa_id'),
        'regla_distribucion',
        ['empresa_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_regla_distribucion_codigo_emision'),
        'regla_distribucion',
        ['codigo_emision'],
        unique=False,
    )
    # Una regla por (empresa, emisión, sucursal). Parciales porque los NULL
    # no colisionan entre sí: sin el segundo índice habría dos reglas
    # generales de la misma emisión y el hecho llegaría dos veces.
    op.create_index(
        'uq_regla_por_sucursal',
        'regla_distribucion',
        ['empresa_id', 'codigo_emision', 'sucursal_id'],
        unique=True,
        sqlite_where=sa.text('sucursal_id IS NOT NULL'),
        postgresql_where=sa.text('sucursal_id IS NOT NULL'),
    )
    op.create_index(
        'uq_regla_general',
        'regla_distribucion',
        ['empresa_id', 'codigo_emision'],
        unique=True,
        sqlite_where=sa.text('sucursal_id IS NULL'),
        postgresql_where=sa.text('sucursal_id IS NULL'),
    )

    op.create_table(
        'regla_destinatario',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('regla_id', sa.Uuid(), nullable=False),
        sa.Column(
            'tipo',
            sa.Enum(
                'area',
                'rol',
                'usuario',
                'dinamico',
                name='tipo_destinatario',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('area_id', sa.Uuid(), nullable=True),
        sa.Column('rol_id', sa.Uuid(), nullable=True),
        sa.Column('usuario_id', sa.Uuid(), nullable=True),
        sa.Column('dinamico', sa.String(length=40), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "(tipo = 'area'     AND area_id     IS NOT NULL) OR "
            "(tipo = 'rol'      AND rol_id      IS NOT NULL) OR "
            "(tipo = 'usuario'  AND usuario_id  IS NOT NULL) OR "
            "(tipo = 'dinamico' AND dinamico    IS NOT NULL)",
            name='ck_regla_destinatario_referencia',
        ),
        sa.ForeignKeyConstraint(['area_id'], ['area.id']),
        sa.ForeignKeyConstraint(['regla_id'], ['regla_distribucion.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rol_id'], ['rol.id']),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_regla_destinatario_regla_id'),
        'regla_destinatario',
        ['regla_id'],
        unique=False,
    )

    op.create_table(
        'reporte_emitido',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('empresa_id', sa.Uuid(), nullable=True),
        sa.Column('sucursal_id', sa.Uuid(), nullable=True),
        sa.Column('codigo_emision', sa.String(length=60), nullable=False),
        sa.Column('titulo', sa.String(length=200), nullable=False),
        sa.Column('cuerpo', sa.Text(), nullable=True),
        sa.Column(
            'nivel',
            sa.Enum('info', 'aviso', 'urgente', name='nivel_reporte', native_enum=False),
            nullable=False,
        ),
        sa.Column(
            'datos',
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), 'postgresql'),
            nullable=False,
        ),
        sa.Column('referencia_tipo', sa.String(length=50), nullable=True),
        sa.Column('referencia_id', sa.Uuid(), nullable=True),
        sa.Column('regla_id', sa.Uuid(), nullable=True),
        sa.Column(
            'emitido_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id']),
        sa.ForeignKeyConstraint(['regla_id'], ['regla_distribucion.id']),
        sa.ForeignKeyConstraint(['sucursal_id'], ['sucursal.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_reporte_emitido_empresa',
        'reporte_emitido',
        ['empresa_id', 'emitido_at'],
        unique=False,
    )
    op.create_index(
        'ix_reporte_emitido_codigo',
        'reporte_emitido',
        ['codigo_emision', 'emitido_at'],
        unique=False,
    )

    op.create_table(
        'entrega_reporte',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('reporte_emitido_id', sa.Uuid(), nullable=False),
        sa.Column('usuario_id', sa.Uuid(), nullable=False),
        sa.Column('motivo', sa.String(length=60), nullable=False),
        sa.Column(
            'canal',
            sa.Enum('bandeja', name='canal_entrega', native_enum=False),
            nullable=False,
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ['reporte_emitido_id'], ['reporte_emitido.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'reporte_emitido_id', 'usuario_id', name='uq_entrega_reporte_usuario'
        ),
    )
    op.create_index(
        op.f('ix_entrega_reporte_reporte_emitido_id'),
        'entrega_reporte',
        ['reporte_emitido_id'],
        unique=False,
    )
    op.create_index('ix_entrega_usuario', 'entrega_reporte', ['usuario_id'], unique=False)


def downgrade() -> None:
    # Orden inverso de las FK: entrega → emitido → destinatario → regla →
    # miembro → area.
    op.drop_index('ix_entrega_usuario', table_name='entrega_reporte')
    op.drop_index(
        op.f('ix_entrega_reporte_reporte_emitido_id'), table_name='entrega_reporte'
    )
    op.drop_table('entrega_reporte')

    op.drop_index('ix_reporte_emitido_codigo', table_name='reporte_emitido')
    op.drop_index('ix_reporte_emitido_empresa', table_name='reporte_emitido')
    op.drop_table('reporte_emitido')

    op.drop_index(
        op.f('ix_regla_destinatario_regla_id'), table_name='regla_destinatario'
    )
    op.drop_table('regla_destinatario')

    op.drop_index('uq_regla_general', table_name='regla_distribucion')
    op.drop_index('uq_regla_por_sucursal', table_name='regla_distribucion')
    op.drop_index(
        op.f('ix_regla_distribucion_codigo_emision'), table_name='regla_distribucion'
    )
    op.drop_index(
        op.f('ix_regla_distribucion_empresa_id'), table_name='regla_distribucion'
    )
    op.drop_table('regla_distribucion')

    op.drop_index(op.f('ix_area_miembro_area_id'), table_name='area_miembro')
    op.drop_table('area_miembro')

    op.drop_index(op.f('ix_area_empresa_id'), table_name='area')
    op.drop_table('area')
