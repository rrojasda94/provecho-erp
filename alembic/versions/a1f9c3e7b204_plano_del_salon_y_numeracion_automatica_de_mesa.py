"""plano del salón y numeración automática de mesa

Completa el CRUD de `mesa` (ADR-018 la creó solo con alta manual):

- `pos_x`/`pos_y`: celda del plano del salón, base 0. El backfill las
  deriva del `numero` que ya existe (`(numero-1) % 12`, `(numero-1) // 12`)
  para que las mesas de demo/producción aparezcan ya ordenadas en el
  croquis. Únicas por sucursal: dos mesas no comparten celda.
- Se quita `mesa.deleted_at`: nunca se escribía (`SoftDeleteMixin` era una
  segunda fuente de verdad muerta) — una mesa se borra de verdad si nunca
  tuvo ventas, o queda `activa=False` si las tuvo (RN-MDC-004/006).

Revision ID: a1f9c3e7b204
Revises: c4d17b93e0af
Create Date: 2026-08-27

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a1f9c3e7b204'
down_revision: str | None = 'c4d17b93e0af'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('mesa', sa.Column('pos_x', sa.Integer(), nullable=True))
    op.add_column('mesa', sa.Column('pos_y', sa.Integer(), nullable=True))
    op.execute(
        "UPDATE mesa SET pos_x = (numero - 1) % 12, pos_y = (numero - 1) / 12"
    )
    op.alter_column('mesa', 'pos_x', nullable=False, server_default='0')
    op.alter_column('mesa', 'pos_y', nullable=False, server_default='0')
    op.create_unique_constraint(
        'uq_mesa_sucursal_posicion', 'mesa', ['sucursal_id', 'pos_x', 'pos_y']
    )
    op.drop_column('mesa', 'deleted_at')


def downgrade() -> None:
    op.add_column('mesa', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint('uq_mesa_sucursal_posicion', 'mesa', type_='unique')
    op.drop_column('mesa', 'pos_y')
    op.drop_column('mesa', 'pos_x')
