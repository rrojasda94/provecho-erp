"""Compra directa (ADR-082): sustenta un gasto ya incurrido con el
comprobante recibido, sin pasar por una OC previa en borrador/emisión.
Reutiliza `OrdenCompra` con `origen="directa"` para no duplicar el
contrato de eventos que ya consumen `inventory` y `accounting`."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.purchases.application import comprobantes as comprobantes_uc
from src.modules.purchases.application import ordenes as ordenes_uc
from src.modules.purchases.application.errors import NoEncontrado
from src.modules.purchases.infrastructure.models import OrdenCompra
from src.modules.purchases.infrastructure.repositories import (
    OrdenCompraRepo,
    ProveedorRepo,
)
from src.modules.users.infrastructure.models import Almacen
from src.shared.models import Comprobante


def registrar_compra_directa(
    session: Session,
    *,
    proveedor_id: uuid.UUID,
    almacen_destino_id: uuid.UUID,
    creado_por: uuid.UUID,
    idempotency_key: str,
    items: list[dict],  # [{articulo_id, cantidad, costo_unitario}]
    comprobante: dict,  # {idempotency_key, tipo, serie, correlativo, sustento}
) -> Comprobante:
    repo = OrdenCompraRepo(session)
    existente = repo.get_by_idempotency(idempotency_key)
    if existente is not None:
        comprobante_existente = session.scalar(
            select(Comprobante).where(Comprobante.compra_id == existente.id)
        )
        if comprobante_existente is not None:
            return comprobante_existente

    proveedor = ProveedorRepo(session).get(proveedor_id)
    if proveedor is None or not proveedor.activo:
        raise NoEncontrado(f"proveedor {proveedor_id} no encontrado")
    if session.get(Almacen, almacen_destino_id) is None:
        raise NoEncontrado(f"almacén {almacen_destino_id} no encontrado")

    filas, total = ordenes_uc.construir_items(session, items)

    orden = OrdenCompra(
        proveedor_id=proveedor_id,
        tipo="insumo",
        origen="directa",
        almacen_destino_id=almacen_destino_id,
        estado="borrador",
        total=total,
        creado_por=creado_por,
        idempotency_key=idempotency_key,
    )
    repo.add(orden)
    for fila in filas:
        fila.orden_compra_id = orden.id
        session.add(fila)
    session.flush()

    # Gasto ya incurrido, no un compromiso a aprobar: pasa directo a
    # emitida, sin el umbral de `emitir_orden_compra`.
    orden.estado = "emitida"
    session.flush()

    recepcion_items = [
        {
            # `orden_compra_item_id` queda como UUID, no str: `recibir_orden_compra`
            # indexa sus ítems por `OrdenCompraItem.id` (UUID) — igual que el router
            # normal, que llega acá vía `RecepcionItemIn.model_dump()`.
            "orden_compra_item_id": fila.id,
            "cantidad_recibida": str(fila.cantidad),
            "costo_unitario": str(fila.costo_unitario),
        }
        for fila in filas
    ]
    ordenes_uc.recibir_orden_compra(
        session,
        orden.id,
        recibido_por=creado_por,
        idempotency_key=f"{idempotency_key}-recepcion",
        items=recepcion_items,
    )

    return comprobantes_uc.dar_conformidad_comprobante(
        session,
        orden.id,
        idempotency_key=comprobante["idempotency_key"],
        tipo=comprobante["tipo"],
        serie=comprobante["serie"],
        correlativo=comprobante["correlativo"],
        sustento=comprobante["sustento"],
    )
