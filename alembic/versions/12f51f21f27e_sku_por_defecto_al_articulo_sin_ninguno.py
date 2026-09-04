"""un SKU por defecto para el artículo que quedó sin ninguno (RN-PRD-006)

Migración de DATOS, no de esquema. `stock` y `movimiento_inventario` cuelgan
de `sku_id`, así que un artículo sin SKU es inerte y en silencio: no tiene
existencias que ver, no entra en un conteo y la recepción de una compra lo
saltea anotando una incidencia `sin_sku`. En staging entraron 244 artículos
así —la hoja «SKUs» de la planilla es opcional— y el módulo de inventario
entero parecía roto.

El código sale del `id_interno`, que ya es único y es lo que la gente lee en
el estante. Los servicios quedan fuera a propósito: no tienen existencias
(`catalogo.crear_sku` los rechaza).

Sin `downgrade` que borre: un SKU nunca se elimina (RN-PRD-006), y para
cuando alguien revierta esto ya puede haber stock y movimientos colgando de
estas filas.

Revision ID: 12f51f21f27e
Revises: c9f4a2e70b18
Create Date: 2026-08-31 12:00:00.000000

"""
import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '12f51f21f27e'
down_revision: str | None = 'c9f4a2e70b18'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIPO_SERVICIO = "servicio"


def upgrade() -> None:
    conexion = op.get_bind()
    huerfanos = conexion.execute(
        sa.text(
            """
            SELECT a.id, a.id_interno
              FROM articulo a
             WHERE a.tipo <> :servicio
               AND NOT EXISTS (SELECT 1 FROM sku s WHERE s.articulo_id = a.id)
             ORDER BY a.id_interno
            """
        ),
        {"servicio": TIPO_SERVICIO},
    ).fetchall()
    if not huerfanos:
        return

    ocupados = {
        fila[0] for fila in conexion.execute(sa.text("SELECT codigo FROM sku"))
    }
    for articulo_id, id_interno in huerfanos:
        codigo = id_interno
        sufijo = 0
        while codigo in ocupados:
            sufijo += 1
            codigo = f"{id_interno}-{sufijo}"
        ocupados.add(codigo)
        conexion.execute(
            sa.text(
                """
                INSERT INTO sku (id, articulo_id, codigo, codigo_barras,
                                 prioridad, activo)
                VALUES (:id, :articulo_id, :codigo, NULL, 1, true)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "articulo_id": str(articulo_id),
                "codigo": codigo,
            },
        )


def downgrade() -> None:
    """No borra nada: ver el encabezado."""
