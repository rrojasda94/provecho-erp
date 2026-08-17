"""la caja la abre el cajero

Revision ID: c8b41f60d2a7
Revises: b2e91f7c40aa
Create Date: 2026-08-15 10:40:00.000000

Una sola columna: `apertura_caja.relevo_encargado_id` pasa a ser NULLABLE.

Desde RN-MDP-008 (ADR-049) el cajero abre y cierra su turno solo, así que la
apertura ya no tiene un encargado que la firme. La columna se conserva —las
aperturas anteriores sí tienen quién firmó, y esa evidencia no se borra—
pero las nuevas la dejan en NULL. Escribir ahí al propio cajero habría
"llenado" la columna al precio de inventar una contraparte, que es
exactamente el dato falso que la firma existía para evitar.

**Sin migración de estados de custodia**: `custodia_efectivo.estado` ya
admitía `en_caja` desde que se creó la tabla (es el primer valor del enum),
así que el cambio de "nace en `en_supervisor`" a "nace en `en_caja`" es solo
código. Las custodias ya escritas se quedan donde están: el efectivo de un
turno viejo sí pasó por la firma del encargado al cerrar.

El `downgrade()` rellena con `cajero_id` antes de volver a NOT NULL: sin eso
la vuelta atrás falla contra cualquier base que haya operado con esta
revisión. Es un valor de relleno y no una afirmación — el motivo por el que
esta migración va en un solo sentido en la práctica.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c8b41f60d2a7'
down_revision: str | None = 'b2e91f7c40aa'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        'apertura_caja',
        'relevo_encargado_id',
        existing_type=sa.Uuid(),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        'UPDATE apertura_caja SET relevo_encargado_id = cajero_id '
        'WHERE relevo_encargado_id IS NULL'
    )
    op.alter_column(
        'apertura_caja',
        'relevo_encargado_id',
        existing_type=sa.Uuid(),
        nullable=False,
    )
