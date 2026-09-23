"""A cuánto se compró un artículo cada vez que entró.

Sale de la recepción y no de la OC: el precio que vale es el que se pagó al
recibir (la recepción puede corregir el costo pactado), y una OC emitida que
nunca llegó no es una compra. La compra directa reutiliza `orden_compra`
(ADR-082), así que entra sola.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.purchases.infrastructure.models import (
    OrdenCompra,
    OrdenCompraItem,
    Proveedor,
    RecepcionCompra,
    RecepcionItem,
)


def historial_precios(
    session: Session,
    articulo_id: uuid.UUID,
    *,
    empresa_id: uuid.UUID | None,
    desde: date | None = None,
) -> list[dict]:
    """Cada recepción del artículo, de la más vieja a la más nueva.

    El alcance lo da el proveedor (ADR-004): un `articulo_id` de otra empresa
    devuelve una lista vacía, igual que uno que nunca se compró.
    """
    consulta = (
        select(
            RecepcionCompra.fecha,
            RecepcionItem.costo_unitario,
            RecepcionItem.cantidad_recibida,
            OrdenCompra.id,
            Proveedor.id,
            Proveedor.razon_social,
        )
        .join(OrdenCompraItem, OrdenCompraItem.id == RecepcionItem.orden_compra_item_id)
        .join(RecepcionCompra, RecepcionCompra.id == RecepcionItem.recepcion_compra_id)
        .join(OrdenCompra, OrdenCompra.id == OrdenCompraItem.orden_compra_id)
        .join(Proveedor, Proveedor.id == OrdenCompra.proveedor_id)
        .where(OrdenCompraItem.articulo_id == articulo_id, RecepcionItem.cantidad_recibida > 0)
        .order_by(RecepcionCompra.fecha, RecepcionItem.id)
    )
    if empresa_id is not None:
        consulta = consulta.where(Proveedor.empresa_id == empresa_id)
    if desde is not None:
        consulta = consulta.where(RecepcionCompra.fecha >= desde)
    return [
        {
            "fecha": fecha,
            "costo_unitario": costo,
            "cantidad": cantidad,
            "orden_compra_id": orden_id,
            "proveedor_id": proveedor_id,
            # Un proveedor natural no tiene razón social: su nombre vive en
            # `persona` (RN-GEN-007), fuera de este módulo. La pantalla ya
            # resuelve nombres por `proveedor_id`.
            "proveedor": razon_social,
        }
        for fecha, costo, cantidad, orden_id, proveedor_id, razon_social in session.execute(
            consulta
        ).all()
    ]
