"""modulo supervision: tareas de apertura/cierre, checklist y evidencia

Módulo nuevo (ADR-102): programación de tareas de apertura y cierre de
sucursal por categoría y frecuencia, con checklist y evidencia fotográfica
opcional. Cuatro tablas, todas aditivas.

`categoria_tarea`: catálogo libre por empresa (limpieza, apertura,
mantenimiento...), sin valores fijos en código.

`tarea_plantilla`: qué se hace, en qué momento (apertura/cierre), con qué
frecuencia (diaria/interdiaria/semanal/mensual) y con qué checklist.
`orden` se puede repetir (tareas en paralelo). Alcanza a una sucursal o a
toda una marca (`sucursal_id` NULL).

`tarea_instancia`: la tarea del día que el trabajador realmente marca.
Puede venir de una plantilla o crearse a mano (`plantilla_id` NULL). Único
parcial `(plantilla_id, sucursal_id, fecha)` para que la generación diaria
sea idempotente por sucursal —una plantilla de marca genera una instancia
por cada sucursal de la marca el mismo día— sin impedir que una tarea
manual se repita el mismo día. La
foto vive acá (`LargeBinary`, comprimida y sin EXIF por el servidor) junto
con la fecha de captura leída del EXIF y si cayó dentro de la ventana de
tolerancia al completar.

`informe_diario`: el resumen de una sucursal al cerrar la jornada — la
entidad a la que apunta el reporte que entra al módulo `reports`.

Revision ID: d518f6efa2ce
Revises: 74e3f09568a0
Create Date: 2026-09-17 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'd518f6efa2ce'
down_revision: str | None = '74e3f09568a0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'categoria_tarea',
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column('nombre', sa.String(length=80), nullable=False),
        sa.Column('activa', sa.Boolean(), nullable=False),
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
            ['empresa_id'], ['empresa.id'],
            name=op.f('fk_categoria_tarea_empresa_id_empresa'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_categoria_tarea')),
        sa.UniqueConstraint(
            'empresa_id', 'nombre', name=op.f('uq_categoria_tarea_empresa_id')
        ),
    )
    op.create_table(
        'tarea_plantilla',
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column('marca_id', sa.Uuid(), nullable=True),
        sa.Column('sucursal_id', sa.Uuid(), nullable=True),
        sa.Column('categoria_id', sa.Uuid(), nullable=False),
        sa.Column('nombre', sa.String(length=120), nullable=False),
        sa.Column('descripcion', sa.String(length=500), nullable=True),
        sa.Column(
            'momento',
            sa.Enum('apertura', 'cierre', name='momento_tarea_plantilla', native_enum=False),
            nullable=False,
        ),
        sa.Column('orden', sa.Integer(), nullable=False),
        sa.Column(
            'frecuencia',
            sa.Enum(
                'diaria', 'interdiaria', 'semanal', 'mensual',
                name='frecuencia_tarea_plantilla', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('dia_semana', sa.Integer(), nullable=True),
        sa.Column('dia_mes', sa.Integer(), nullable=True),
        sa.Column('fecha_inicio', sa.Date(), nullable=False),
        sa.Column('requiere_foto', sa.Boolean(), nullable=False),
        sa.Column(
            'checklist',
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
            nullable=False,
        ),
        sa.Column('asignado_a', sa.Uuid(), nullable=True),
        sa.Column('activa', sa.Boolean(), nullable=False),
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
            'sucursal_id IS NOT NULL OR marca_id IS NOT NULL',
            name=op.f('ck_tarea_plantilla_alcance_tarea_plantilla'),
        ),
        sa.CheckConstraint(
            "momento IN ('apertura', 'cierre')",
            name=op.f('ck_tarea_plantilla_momento_tarea_plantilla'),
        ),
        sa.CheckConstraint(
            "frecuencia IN ('diaria', 'interdiaria', 'semanal', 'mensual')",
            name=op.f('ck_tarea_plantilla_frecuencia_tarea_plantilla'),
        ),
        sa.CheckConstraint(
            'dia_semana IS NULL OR (dia_semana >= 0 AND dia_semana <= 6)',
            name=op.f('ck_tarea_plantilla_dia_semana_tarea_plantilla'),
        ),
        sa.CheckConstraint(
            'dia_mes IS NULL OR (dia_mes >= 1 AND dia_mes <= 28)',
            name=op.f('ck_tarea_plantilla_dia_mes_tarea_plantilla'),
        ),
        sa.ForeignKeyConstraint(
            ['asignado_a'], ['usuario.id'],
            name=op.f('fk_tarea_plantilla_asignado_a_usuario'),
        ),
        sa.ForeignKeyConstraint(
            ['categoria_id'], ['categoria_tarea.id'],
            name=op.f('fk_tarea_plantilla_categoria_id_categoria_tarea'),
        ),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresa.id'],
            name=op.f('fk_tarea_plantilla_empresa_id_empresa'),
        ),
        sa.ForeignKeyConstraint(
            ['marca_id'], ['marca.id'],
            name=op.f('fk_tarea_plantilla_marca_id_marca'),
        ),
        sa.ForeignKeyConstraint(
            ['sucursal_id'], ['sucursal.id'],
            name=op.f('fk_tarea_plantilla_sucursal_id_sucursal'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tarea_plantilla')),
    )
    op.create_table(
        'tarea_instancia',
        sa.Column('plantilla_id', sa.Uuid(), nullable=True),
        sa.Column('sucursal_id', sa.Uuid(), nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column(
            'momento',
            sa.Enum('apertura', 'cierre', name='momento_tarea_instancia', native_enum=False),
            nullable=False,
        ),
        sa.Column('orden', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=120), nullable=False),
        sa.Column('categoria_id', sa.Uuid(), nullable=False),
        sa.Column('requiere_foto', sa.Boolean(), nullable=False),
        sa.Column(
            'checklist',
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
            nullable=False,
        ),
        sa.Column('asignado_a', sa.Uuid(), nullable=True),
        sa.Column(
            'estado',
            sa.Enum(
                'pendiente', 'completada', 'vencida',
                name='estado_tarea_instancia', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('completada_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completada_por', sa.Uuid(), nullable=True),
        sa.Column('foto', sa.LargeBinary(), nullable=True),
        sa.Column('foto_tomada_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('foto_valida', sa.Boolean(), nullable=True),
        sa.Column('observacion', sa.String(length=255), nullable=True),
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
            "momento IN ('apertura', 'cierre')",
            name=op.f('ck_tarea_instancia_momento_tarea_instancia'),
        ),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'completada', 'vencida')",
            name=op.f('ck_tarea_instancia_estado_tarea_instancia'),
        ),
        sa.ForeignKeyConstraint(
            ['asignado_a'], ['usuario.id'],
            name=op.f('fk_tarea_instancia_asignado_a_usuario'),
        ),
        sa.ForeignKeyConstraint(
            ['categoria_id'], ['categoria_tarea.id'],
            name=op.f('fk_tarea_instancia_categoria_id_categoria_tarea'),
        ),
        sa.ForeignKeyConstraint(
            ['completada_por'], ['usuario.id'],
            name=op.f('fk_tarea_instancia_completada_por_usuario'),
        ),
        sa.ForeignKeyConstraint(
            ['plantilla_id'], ['tarea_plantilla.id'],
            name=op.f('fk_tarea_instancia_plantilla_id_tarea_plantilla'),
        ),
        sa.ForeignKeyConstraint(
            ['sucursal_id'], ['sucursal.id'],
            name=op.f('fk_tarea_instancia_sucursal_id_sucursal'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tarea_instancia')),
    )
    op.create_index(
        'uq_tarea_instancia_plantilla_sucursal_fecha',
        'tarea_instancia',
        ['plantilla_id', 'sucursal_id', 'fecha'],
        unique=True,
        postgresql_where=sa.text('plantilla_id IS NOT NULL'),
        sqlite_where=sa.text('plantilla_id IS NOT NULL'),
    )
    op.create_table(
        'informe_diario',
        sa.Column('sucursal_id', sa.Uuid(), nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('total', sa.Integer(), nullable=False),
        sa.Column('completadas', sa.Integer(), nullable=False),
        sa.Column('vencidas', sa.Integer(), nullable=False),
        sa.Column('fotos_invalidas', sa.Integer(), nullable=False),
        sa.Column('generado_at', sa.DateTime(timezone=True), nullable=False),
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
            ['sucursal_id'], ['sucursal.id'],
            name=op.f('fk_informe_diario_sucursal_id_sucursal'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_informe_diario')),
        sa.UniqueConstraint(
            'sucursal_id', 'fecha', name=op.f('uq_informe_diario_sucursal_id')
        ),
    )


def downgrade() -> None:
    op.drop_table('informe_diario')
    op.drop_index('uq_tarea_instancia_plantilla_sucursal_fecha', table_name='tarea_instancia')
    op.drop_table('tarea_instancia')
    op.drop_table('tarea_plantilla')
    op.drop_table('categoria_tarea')
