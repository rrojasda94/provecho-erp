"""retirar regla_aprobacion: sus umbrales pasan a parametro_empresa

`parametro_empresa` (ADR-014 + Addendum) cubre lo mismo con un flujo de
aprobación de Gerencia; mantener dos tablas de configuración sobrevivía solo
por inercia. Las filas vigentes se copian como parámetros ya aprobados
(`estado='vigente'`, `valor={"monto": umbral}`) y se atribuyen al usuario
`admin` — no hay un proponente real que reconstruir.

`permiso_requerido` se pierde a propósito: era informativo (la verificación
real siempre la hizo el módulo consumidor, ver su docstring original).

Revision ID: b82d4c1f7a35
Revises: a71c9f4b2e60
Create Date: 2026-08-02 12:00:00.000000

"""
import uuid
from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'b82d4c1f7a35'
down_revision: str | None = 'a71c9f4b2e60'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')

_regla = sa.table(
    'regla_aprobacion',
    sa.column('empresa_id', sa.Uuid()),
    sa.column('modulo', sa.String()),
    sa.column('codigo', sa.String()),
    sa.column('umbral', sa.Numeric()),
    sa.column('permiso_requerido', sa.String()),
    sa.column('vigente', sa.Boolean()),
)
_parametro = sa.table(
    'parametro_empresa',
    sa.column('id', sa.Uuid()),
    sa.column('empresa_id', sa.Uuid()),
    sa.column('modulo', sa.String()),
    sa.column('codigo', sa.String()),
    sa.column('valor', _JSON),
    sa.column('estado', sa.String()),
    sa.column('propuesto_por_id', sa.Uuid()),
    sa.column('motivo', sa.Text()),
    sa.column('resuelto_por_id', sa.Uuid()),
    sa.column('resuelto_en', sa.DateTime(timezone=True)),
)
_usuario = sa.table('usuario', sa.column('id', sa.Uuid()), sa.column('username', sa.String()))


def upgrade() -> None:
    bind = op.get_bind()
    admin_id = bind.scalar(sa.select(_usuario.c.id).where(_usuario.c.username == 'admin'))
    reglas = bind.execute(
        sa.select(_regla.c.empresa_id, _regla.c.modulo, _regla.c.codigo, _regla.c.umbral)
        .where(_regla.c.vigente.is_(True))
    ).all()
    if reglas and admin_id is None:
        raise RuntimeError(
            "hay reglas de aprobación vigentes pero no existe el usuario 'admin' "
            "al cual atribuirlas; correr el seeder antes de esta migración"
        )
    ahora = sa.func.current_timestamp()  # portable; `now()` no existe en SQLite
    for empresa_id, modulo, codigo, umbral in reglas:
        # Ya migrado o pisado a mano: no duplicar el vigente.
        existe = bind.scalar(
            sa.select(sa.func.count())
            .select_from(_parametro)
            .where(
                _parametro.c.empresa_id == empresa_id,
                _parametro.c.modulo == modulo,
                _parametro.c.codigo == codigo,
                _parametro.c.estado == 'vigente',
            )
        )
        if existe:
            continue
        bind.execute(
            _parametro.insert().values(
                id=uuid.uuid4(),
                empresa_id=empresa_id,
                modulo=modulo,
                codigo=codigo,
                # Canónico a 2 decimales: la escala que devuelve el driver
                # varía por dialecto y el monto viaja como texto en el JSON.
                valor={"monto": str(Decimal(umbral).quantize(Decimal("0.01")))},
                estado='vigente',
                propuesto_por_id=admin_id,
                motivo='migrado desde regla_aprobacion',
                resuelto_por_id=admin_id,
                resuelto_en=ahora,
            )
        )

    op.drop_table('regla_aprobacion')


def downgrade() -> None:
    op.create_table(
        'regla_aprobacion',
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column('modulo', sa.String(length=50), nullable=False),
        sa.Column('codigo', sa.String(length=50), nullable=False),
        sa.Column('umbral', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('permiso_requerido', sa.String(length=100), nullable=False),
        sa.Column('vigente', sa.Boolean(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id'], name=op.f('fk_regla_aprobacion_empresa_id_empresa')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_regla_aprobacion')),
        sa.UniqueConstraint('empresa_id', 'modulo', 'codigo', name=op.f('uq_regla_aprobacion_empresa_id')),
    )
    # Los parámetros migrados no vuelven: `permiso_requerido` ya no existe y
    # reconstruirlo sería inventar dato. La tabla vuelve vacía.
