"""turno de trabajo y pad de asistencia

Crea `turno_sucursal` (horario laboral por local, ADR-064) y engancha la
asistencia a el: `asistencia.turno_id` dice contra que turno se midio la
tardanza, y `asistencia.reporte_salida_en` sella el aviso de salida sin
marcar para que el barrido no avise dos veces por lo mismo.

Las dos columnas son nullable: las marcaciones que ya existen no tienen
turno, y una correccion a mano de RRHH puede seguir sin tenerlo.

Revision ID: c4d17b93e0af
Revises: b6d29f10c47e
Create Date: 2026-08-24

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c4d17b93e0af'
down_revision: str | None = 'ce32c6610eb7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'turno_sucursal',
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column('sucursal_id', sa.Uuid(), nullable=False),
        sa.Column('nombre', sa.String(length=50), nullable=False),
        sa.Column('hora_inicio', sa.Time(), nullable=False),
        sa.Column('hora_fin', sa.Time(), nullable=False),
        sa.Column('tolerancia_min', sa.Integer(), nullable=False),
        sa.Column('hora_limite_salida', sa.Time(), nullable=False),
        sa.Column('activo', sa.Boolean(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
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
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresa.id'],
            name=op.f('fk_turno_sucursal_empresa_id_empresa'),
        ),
        sa.ForeignKeyConstraint(
            ['sucursal_id'], ['sucursal.id'],
            name=op.f('fk_turno_sucursal_sucursal_id_sucursal'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_turno_sucursal')),
        sa.UniqueConstraint(
            'sucursal_id', 'nombre', name=op.f('uq_turno_sucursal_sucursal_id')
        ),
    )
    op.add_column('asistencia', sa.Column('turno_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f('fk_asistencia_turno_id_turno_sucursal'),
        'asistencia',
        'turno_sucursal',
        ['turno_id'],
        ['id'],
    )
    op.add_column(
        'asistencia',
        sa.Column('reporte_salida_en', sa.DateTime(timezone=True), nullable=True),
    )
    # El nombre de una pantalla KDS borrada vuelve a estar libre: el UNIQUE
    # plano lo dejaba tomado para siempre, y desde hoy la pantalla se puede
    # borrar de verdad (`deleted_at`), no solo desactivar.
    op.drop_constraint(
        op.f('uq_kds_pantalla_sucursal_id'), 'kds_pantalla', type_='unique'
    )
    op.create_index(
        'uq_kds_pantalla_viva',
        'kds_pantalla',
        ['sucursal_id', 'nombre'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
        sqlite_where=sa.text('deleted_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_kds_pantalla_viva', table_name='kds_pantalla')
    op.create_unique_constraint(
        op.f('uq_kds_pantalla_sucursal_id'), 'kds_pantalla', ['sucursal_id', 'nombre']
    )
    op.drop_column('asistencia', 'reporte_salida_en')
    op.drop_constraint(
        op.f('fk_asistencia_turno_id_turno_sucursal'), 'asistencia', type_='foreignkey'
    )
    op.drop_column('asistencia', 'turno_id')
    op.drop_table('turno_sucursal')
