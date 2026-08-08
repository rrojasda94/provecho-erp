"""audit_log transversal: empresa_id e índices de consulta

Revision ID: b3d9f1c2a077
Revises: e7c390a5b41f
Create Date: 2026-08-08 10:00:00.000000

El `audit_log` deja de ser una tabla de `users` y pasa a `shared` (ADR-029).
La tabla es la misma; lo que cambia acá es lo que hacía falta para que
*todos* los módulos escriban y alguien pueda leer:

- **`empresa_id`** (nullable): sin él, la lectura del rastro no se puede
  escopar por tenant (ADR-004) y un contador vería el de otra empresa.
  Nullable porque no todo hecho auditable tiene empresa — un login fallido
  todavía no la tiene, y un alta de rol es global; esas filas solo las ve
  un superusuario.
- **`ix_audit_log_entidad`** (`entidad`, `entidad_id`): "todo lo que le pasó
  a esta venta".
- **`ix_audit_log_ts`**: el listado por defecto, siempre por fecha. Con la
  tabla creciendo por inserción pura, ordenar sin índice es un scan
  completo que empeora cada día.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'b3d9f1c2a077'
down_revision: str | None = 'e7c390a5b41f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('audit_log', sa.Column('empresa_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f('fk_audit_log_empresa_id_empresa'),
        'audit_log', 'empresa', ['empresa_id'], ['id'],
    )
    op.create_index('ix_audit_log_entidad', 'audit_log', ['entidad', 'entidad_id'])
    op.create_index('ix_audit_log_ts', 'audit_log', ['ts'])


def downgrade() -> None:
    op.drop_index('ix_audit_log_ts', table_name='audit_log')
    op.drop_index('ix_audit_log_entidad', table_name='audit_log')
    op.drop_constraint(
        op.f('fk_audit_log_empresa_id_empresa'), 'audit_log', type_='foreignkey'
    )
    op.drop_column('audit_log', 'empresa_id')
