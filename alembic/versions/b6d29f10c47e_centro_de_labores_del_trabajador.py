"""centro de labores del trabajador

Agrega `trabajador.sucursal_id`: donde trabaja la persona (ADR-061). No es el
alcance de datos de su cuenta —eso sigue viviendo en `usuario_sucursal`, del
lado del usuario— sino un hecho laboral: manda en asistencia, en el contrato y
en los reemplazos entre locales (RN-RRHH-011).

Nullable: gerencia y administracion no estan en ningun local, y los
trabajadores que ya existen no tienen sucursal asignada.

Revision ID: b6d29f10c47e
Revises: e2b7c40d91af
Create Date: 2026-08-24

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b6d29f10c47e'
down_revision: str | None = 'e2b7c40d91af'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('trabajador', sa.Column('sucursal_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f('fk_trabajador_sucursal_id_sucursal'),
        'trabajador',
        'sucursal',
        ['sucursal_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('fk_trabajador_sucursal_id_sucursal'), 'trabajador', type_='foreignkey'
    )
    op.drop_column('trabajador', 'sucursal_id')
