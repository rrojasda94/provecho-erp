"""encuesta_satisfaccion.empresa_id: de quién es la encuesta

Sin esta columna no hay listado posible: la encuesta cuelga de una venta, la
venta vive en `sales`, y filtrar por tenant sería un join entre módulos. Mismo
criterio con el que `postulante` ganó su `empresa_id`.

Nullable porque las filas anteriores no la tienen; el `UPDATE` de abajo las
rellena por el camino largo —venta → sucursal— que a partir de ahora nadie
tiene que recorrer.

Revision ID: c7a1e94b2d38
Revises: b5e7d1a3c92f
Create Date: 2026-09-05 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'c7a1e94b2d38'
down_revision: str | None = 'b5e7d1a3c92f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('encuesta_satisfaccion') as batch:
        batch.add_column(sa.Column('empresa_id', sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f('fk_encuesta_satisfaccion_empresa_id_empresa'),
            'empresa', ['empresa_id'], ['id'],
        )
    op.create_index(
        op.f('ix_encuesta_satisfaccion_empresa_id'),
        'encuesta_satisfaccion',
        ['empresa_id'],
    )
    # El backfill es la razón de que la columna pueda ser NULL sin esconder
    # datos: una encuesta vieja aparece igual en el listado de su empresa.
    op.execute(
        """
        UPDATE encuesta_satisfaccion
           SET empresa_id = (
               SELECT sucursal.empresa_id
                 FROM venta
                 JOIN sucursal ON sucursal.id = venta.sucursal_id
                WHERE venta.id = encuesta_satisfaccion.venta_id
           )
         WHERE empresa_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_encuesta_satisfaccion_empresa_id'), 'encuesta_satisfaccion'
    )
    with op.batch_alter_table('encuesta_satisfaccion') as batch:
        batch.drop_constraint(
            op.f('fk_encuesta_satisfaccion_empresa_id_empresa'), type_='foreignkey'
        )
        batch.drop_column('empresa_id')
