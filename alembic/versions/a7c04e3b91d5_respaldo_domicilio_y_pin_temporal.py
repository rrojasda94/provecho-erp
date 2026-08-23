"""abastecedor de respaldo, domicilio del proveedor y PIN temporal

Revision ID: a7c04e3b91d5
Revises: df7fa09a4f62
Create Date: 2026-08-12 15:40:00.000000

Cinco columnas de tres áreas que no se tocan entre sí; van juntas porque son
la misma entrega y una migración por columna solo agrega cabezas que después
hay que repuntar.

- `almacen.almacen_abastecedor_respaldo_id`: a quién se le pide cuando el
  principal no está (RN-INV-022). Auto-FK como el principal, y nullable
  porque tener respaldo es una decisión de cada local, no una obligación.
- `proveedor.direccion` / `provincia` / `pais`: el domicilio fiscal que
  devuelve SUNAT al consultar el RUC. Partido y no en un solo texto porque
  `provincia` es lo que decide si el flete es local o interprovincial.
  `pais` con default `'PE'` y NOT NULL: todo proveedor tiene uno, y el
  extranjero es la excepción que hay que poder declarar.
- `usuario.debe_cambiar_pin`: la cuenta trae un PIN que puso otra persona.
  NOT NULL con default `false` — las cuentas que ya existen eligieron su PIN.

Sin backfill: los cuatro nullables arrancan vacíos y el booleano en `false`,
que es lo que corresponde para todo lo que ya estaba.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a7c04e3b91d5'
down_revision: str | None = 'df7fa09a4f62'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'almacen',
        sa.Column('almacen_abastecedor_respaldo_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'fk_almacen_almacen_abastecedor_respaldo_id_almacen',
        'almacen',
        'almacen',
        ['almacen_abastecedor_respaldo_id'],
        ['id'],
    )

    op.add_column('proveedor', sa.Column('direccion', sa.String(255), nullable=True))
    op.add_column('proveedor', sa.Column('provincia', sa.String(100), nullable=True))
    op.add_column(
        'proveedor',
        sa.Column('pais', sa.String(60), nullable=False, server_default='PE'),
    )

    op.add_column(
        'usuario',
        sa.Column(
            'debe_cambiar_pin',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )


def downgrade() -> None:
    op.drop_column('usuario', 'debe_cambiar_pin')
    op.drop_column('proveedor', 'pais')
    op.drop_column('proveedor', 'provincia')
    op.drop_column('proveedor', 'direccion')
    op.drop_constraint(
        'fk_almacen_almacen_abastecedor_respaldo_id_almacen',
        'almacen',
        type_='foreignkey',
    )
    op.drop_column('almacen', 'almacen_abastecedor_respaldo_id')
