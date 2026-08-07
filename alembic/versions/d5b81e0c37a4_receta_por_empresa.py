"""receta.empresa_id: la ficha técnica pasa a tener dueño

Revision ID: d5b81e0c37a4
Revises: c2f6a94b13de
Create Date: 2026-08-06 15:10:00.000000

`receta` era la única entidad del catálogo de `inventory` sin columna de
tenant: su CRUD listaba las de todas las empresas y el hub de sucursal las
replicaba completas. Con un solo grupo operando no se notaba; con dos
empresas que no deban verse entre sí es una fuga.

El relleno va en tres pasos porque la columna termina siendo NOT NULL y no
se puede agregar así sobre filas existentes:

1. Se agrega nullable.
2. Se rellena desde `articulo.empresa_id` cuando la receta produce una
   subreceta (`receta.articulo_id`), que es el dato duro; el resto se
   atribuye a la **única empresa operativa**. Eso es correcto hoy —el
   seeder crea una sola— y sería incorrecto con dos: si alguna vez se
   corre contra una base multi-empresa, hay que revisar el reparto a mano
   antes de aplicar el paso 3. Se deja dicho acá porque el día que pase,
   este archivo es lo que alguien va a leer.
3. Se pone NOT NULL.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd5b81e0c37a4'
down_revision: str | None = 'c2f6a94b13de'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('receta', sa.Column('empresa_id', sa.Uuid(), nullable=True))

    # 1) Lo que la receta produce sabe de qué empresa es.
    op.execute(
        """
        UPDATE receta
           SET empresa_id = (
               SELECT a.empresa_id FROM articulo a WHERE a.id = receta.articulo_id
           )
         WHERE receta.articulo_id IS NOT NULL
        """
    )
    # 2) Las de venta directa, a la única empresa que existe.
    op.execute(
        """
        UPDATE receta
           SET empresa_id = (SELECT id FROM empresa ORDER BY created_at LIMIT 1)
         WHERE empresa_id IS NULL
        """
    )
    # Una receta sin empresa a esta altura significa base sin empresas: no
    # hay valor razonable que inventar, y dejarla pasar rompería el NOT NULL
    # con un error mucho menos claro que este.
    op.execute(
        """
        DELETE FROM receta_item
         WHERE receta_id IN (SELECT id FROM receta WHERE empresa_id IS NULL)
        """
    )
    op.execute("DELETE FROM receta WHERE empresa_id IS NULL")

    op.alter_column('receta', 'empresa_id', nullable=False)
    op.create_foreign_key(
        'fk_receta_empresa_id_empresa', 'receta', 'empresa', ['empresa_id'], ['id']
    )
    op.create_index(op.f('ix_receta_empresa_id'), 'receta', ['empresa_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_receta_empresa_id'), table_name='receta')
    op.drop_constraint('fk_receta_empresa_id_empresa', 'receta', type_='foreignkey')
    op.drop_column('receta', 'empresa_id')
