"""divisa, unidad_medida.decimales y parametro_empresa.valor_display

Toda magnitud viaja con su unidad y se redondea con los decimales de ESA
unidad, no con una constante del código (RN-GER-010).

`unidad_medida.decimales` arranca en 3: es la precisión que ya usan las
cantidades de inventario (`Numeric(12, 4)` en stock, gramos importan). Cada
unidad puede bajarlo (0 para unidades sueltas) cuando exista su CRUD.

Revision ID: c93e5a7b1d42
Revises: b82d4c1f7a35
Create Date: 2026-08-02 14:00:00.000000

"""
import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'c93e5a7b1d42'
down_revision: str | None = 'b82d4c1f7a35'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_divisa = sa.table(
    'divisa',
    sa.column('id', sa.Uuid()),
    sa.column('codigo', sa.String()),
    sa.column('nombre', sa.String()),
    sa.column('simbolo', sa.String()),
    sa.column('decimales', sa.Integer()),
    sa.column('activa', sa.Boolean()),
)
_parametro = sa.table(
    'parametro_empresa',
    sa.column('id', sa.Uuid()),
    sa.column('valor', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')),
    sa.column('valor_display', sa.String()),
    sa.column('estado', sa.String()),
)


def upgrade() -> None:
    op.create_table(
        'divisa',
        sa.Column('codigo', sa.String(length=3), nullable=False),
        sa.Column('nombre', sa.String(length=50), nullable=False),
        sa.Column('simbolo', sa.String(length=5), nullable=False),
        sa.Column('decimales', sa.Integer(), nullable=False),
        sa.Column('activa', sa.Boolean(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_divisa')),
        sa.UniqueConstraint('codigo', name=op.f('uq_divisa_codigo')),
    )
    # PEN es la moneda de la operación (RN-PRC-004); sin ella ningún monto
    # puede declarar su unidad.
    op.bulk_insert(
        _divisa,
        [{
            'id': uuid.UUID('3f1c8b7a-9d24-4e51-8a63-0c5b2e7f41d9'),
            'codigo': 'PEN',
            'nombre': 'Sol peruano',
            'simbolo': 'S/',
            'decimales': 2,
            'activa': True,
        }],
    )

    op.add_column(
        'unidad_medida',
        sa.Column('decimales', sa.Integer(), nullable=False, server_default='3'),
    )
    op.alter_column('unidad_medida', 'decimales', server_default=None)

    op.add_column(
        'parametro_empresa', sa.Column('valor_display', sa.String(length=120), nullable=True)
    )
    _completar_divisa_de_montos_existentes()


def _completar_divisa_de_montos_existentes() -> None:
    """Los umbrales que llegaron de `regla_aprobacion` (migración
    `b82d4c1f7a35`) son montos sin `divisa`: esa tabla nunca la tuvo. La
    operación es PEN única (RN-PRC-004), así que se completa aquí en vez de
    dejar filas que no cumplen RN-GER-010."""
    bind = op.get_bind()
    filas = bind.execute(
        sa.select(_parametro.c.id, _parametro.c.valor).where(_parametro.c.estado == 'vigente')
    ).all()
    for parametro_id, valor in filas:
        if not isinstance(valor, dict):
            valor = json.loads(valor)  # SQLite guarda el JSON como texto
        monto = next((c for c in ('monto', 'minimo', 'maximo') if c in valor), None)
        if monto is None or valor.get('divisa'):
            continue
        completo = {**valor, 'divisa': 'PEN'}
        display = " – ".join(f"S/ {completo[c]}" for c in ('monto', 'minimo', 'maximo') if c in completo)
        bind.execute(
            _parametro.update()
            .where(_parametro.c.id == parametro_id)
            .values(valor=completo, valor_display=display)
        )


def downgrade() -> None:
    op.drop_column('parametro_empresa', 'valor_display')
    op.drop_column('unidad_medida', 'decimales')
    op.drop_table('divisa')
