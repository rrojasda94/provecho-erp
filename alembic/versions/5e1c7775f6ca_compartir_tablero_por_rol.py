"""compartir tablero por rol

Revision ID: 5e1c7775f6ca
Revises: 998e335369a1
Create Date: 2026-08-04 09:20:38.556609

`tablero.rol_id` NULL = privado, que es el estado de todos los tableros ya
guardados: la columna nace nullable y no hace falta backfill. Con rol, el
tablero lo ve en solo lectura cualquiera que tenga ese rol; editarlo y
borrarlo siguen siendo del dueño (`usuario_id`).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '5e1c7775f6ca'
down_revision: str | None = '998e335369a1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `batch_alter_table`: SQLite no admite ADD CONSTRAINT sobre una tabla
    # existente y necesita recrearla por debajo. En Postgres se traduce a un
    # ALTER normal.
    with op.batch_alter_table('tablero') as batch:
        batch.add_column(sa.Column('rol_id', sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f('fk_tablero_rol_id_rol'), 'rol', ['rol_id'], ['id']
        )
    # "Los tableros compartidos con mis roles" filtra por esta columna en
    # cada carga del dashboard.
    op.create_index(op.f('ix_tablero_rol_id'), 'tablero', ['rol_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_tablero_rol_id'), table_name='tablero')
    with op.batch_alter_table('tablero') as batch:
        batch.drop_constraint(op.f('fk_tablero_rol_id_rol'), type_='foreignkey')
        batch.drop_column('rol_id')
