"""convocatoria y tablero de contratacion: postulante con datos propios,
empresa_id y estados del proceso completo

Revision ID: a7f2c81e4b95
Revises: d8b35f1ca207
Create Date: 2026-08-01 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a7f2c81e4b95'
down_revision: str | None = 'd8b35f1ca207'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'convocatoria',
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column('sucursal_id', sa.Uuid(), nullable=True),
        sa.Column('puesto', sa.String(length=150), nullable=False),
        sa.Column('perfil_puesto', sa.String(length=100), nullable=True),
        sa.Column(
            'motivo',
            sa.Enum(
                'reemplazo',
                'refuerzo',
                'puesto_nuevo',
                name='motivo_convocatoria',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('vacantes', sa.Integer(), nullable=False),
        sa.Column('jornada_horas_semana', sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column('remuneracion_min', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('remuneracion_max', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('fecha_objetivo', sa.Date(), nullable=True),
        sa.Column('fecha_limite', sa.Date(), nullable=True),
        sa.Column('fecha_publicacion', sa.Date(), nullable=True),
        sa.Column('token_publico', sa.String(length=43), nullable=True),
        sa.Column(
            'estado',
            sa.Enum(
                'borrador',
                'publicada',
                'cerrada',
                name='estado_convocatoria',
                native_enum=False,
            ),
            nullable=False,
        ),
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
            ['empresa_id'], ['empresa.id'], name=op.f('fk_convocatoria_empresa_id_empresa')
        ),
        sa.ForeignKeyConstraint(
            ['sucursal_id'], ['sucursal.id'], name=op.f('fk_convocatoria_sucursal_id_sucursal')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_convocatoria')),
        sa.UniqueConstraint('token_publico', name=op.f('uq_convocatoria_token_publico')),
    )
    op.create_index(
        op.f('ix_convocatoria_token_publico'), 'convocatoria', ['token_publico'], unique=True
    )

    # El postulante deja de colgar de `persona`: es gente ajena a la empresa
    # y la mayoría nunca se contrata. Sus datos viven en su propia ficha.
    op.add_column('postulante', sa.Column('empresa_id', sa.Uuid(), nullable=True))
    op.add_column('postulante', sa.Column('convocatoria_id', sa.Uuid(), nullable=True))
    op.add_column('postulante', sa.Column('nombres', sa.String(length=100), nullable=True))
    op.add_column('postulante', sa.Column('apellidos', sa.String(length=100), nullable=True))
    op.add_column('postulante', sa.Column('telefono', sa.String(length=30), nullable=True))
    op.add_column('postulante', sa.Column('email', sa.String(length=150), nullable=True))
    op.add_column('postulante', sa.Column('canal_origen', sa.String(length=50), nullable=True))
    op.add_column(
        'postulante',
        sa.Column(
            'respuestas',
            sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'),
            nullable=True,
        ),
    )
    op.add_column('postulante', sa.Column('trabajador_id', sa.Uuid(), nullable=True))
    op.add_column(
        'postulante', sa.Column('motivo_descarte', sa.String(length=255), nullable=True)
    )

    # Backfill de las filas existentes antes de exigir los NOT NULL.
    op.execute(
        """
        UPDATE postulante SET
            nombres = COALESCE(persona.nombres, 'desconocido'),
            apellidos = COALESCE(persona.apellidos, 'desconocido')
        FROM persona WHERE persona.id = postulante.persona_id
        """
    )
    op.execute("UPDATE postulante SET nombres = 'desconocido' WHERE nombres IS NULL")
    op.execute("UPDATE postulante SET apellidos = 'desconocido' WHERE apellidos IS NULL")
    # Una sola empresa opera hoy; el postulante histórico es suyo.
    op.execute(
        """
        UPDATE postulante
        SET empresa_id = (SELECT id FROM empresa ORDER BY created_at LIMIT 1)
        WHERE empresa_id IS NULL
        """
    )

    op.alter_column('postulante', 'nombres', nullable=False)
    op.alter_column('postulante', 'apellidos', nullable=False)
    op.alter_column('postulante', 'empresa_id', nullable=False)
    op.alter_column('postulante', 'persona_id', existing_type=sa.Uuid(), nullable=True)

    op.create_foreign_key(
        op.f('fk_postulante_empresa_id_empresa'),
        'postulante',
        'empresa',
        ['empresa_id'],
        ['id'],
    )
    op.create_foreign_key(
        op.f('fk_postulante_convocatoria_id_convocatoria'),
        'postulante',
        'convocatoria',
        ['convocatoria_id'],
        ['id'],
    )
    op.create_foreign_key(
        op.f('fk_postulante_trabajador_id_trabajador'),
        'postulante',
        'trabajador',
        ['trabajador_id'],
        ['id'],
    )

    # El tablero reemplaza los tres estados originales.
    op.execute("UPDATE postulante SET estado = 'recibido' WHERE estado = 'en_proceso'")
    op.execute("UPDATE postulante SET estado = 'descartado' WHERE estado = 'rechazado'")


def downgrade() -> None:
    op.execute("UPDATE postulante SET estado = 'rechazado' WHERE estado = 'descartado'")
    op.execute(
        """
        UPDATE postulante SET estado = 'en_proceso'
        WHERE estado NOT IN ('rechazado', 'contratado')
        """
    )
    op.drop_constraint(
        op.f('fk_postulante_trabajador_id_trabajador'), 'postulante', type_='foreignkey'
    )
    op.drop_constraint(
        op.f('fk_postulante_convocatoria_id_convocatoria'), 'postulante', type_='foreignkey'
    )
    op.drop_constraint(
        op.f('fk_postulante_empresa_id_empresa'), 'postulante', type_='foreignkey'
    )
    op.drop_column('postulante', 'motivo_descarte')
    op.drop_column('postulante', 'trabajador_id')
    op.drop_column('postulante', 'respuestas')
    op.drop_column('postulante', 'canal_origen')
    op.drop_column('postulante', 'email')
    op.drop_column('postulante', 'telefono')
    op.drop_column('postulante', 'apellidos')
    op.drop_column('postulante', 'nombres')
    op.drop_column('postulante', 'convocatoria_id')
    op.drop_column('postulante', 'empresa_id')
    # `persona_id` vuelve a ser obligatorio: el postulante sin persona no
    # cabe en el modelo anterior.
    op.execute("DELETE FROM postulante WHERE persona_id IS NULL")
    op.alter_column('postulante', 'persona_id', existing_type=sa.Uuid(), nullable=False)
    op.drop_index(op.f('ix_convocatoria_token_publico'), table_name='convocatoria')
    op.drop_table('convocatoria')
