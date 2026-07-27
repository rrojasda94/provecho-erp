"""Cumplimiento de pedido (PROC-OPE-002): registrar la entrega al cliente.

Cierra el proceso que el KDS empieza. La preparación avanza ítem por ítem
(`application/kds.py`); la entrega es un acto único de la venta completa,
lo ejecuta quien despacha —no la cocina— y es el hecho que Marketing
espera para decidir la encuesta de satisfacción (RN-COM-007).

Idempotente por naturaleza (RN-CUP-005): volver a registrar la entrega de
un pedido ya entregado no reemite el evento.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.sales.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import Venta, VentaItem


def registrar_entrega(
    session: Session, venta_id: uuid.UUID, *, entregado_por: uuid.UUID
) -> dict:
    """Marca el pedido como entregado y publica `sales.venta_entregada`.

    Exige que todos los ítems estén al menos `listo` (RN-CUP-005): un
    pedido a medio preparar no se entrega.
    """
    venta = session.get(Venta, venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    if venta.estado == "anulada":
        raise Conflicto("la venta está anulada")

    items = list(
        session.scalars(select(VentaItem).where(VentaItem.venta_id == venta_id))
    )
    estados = [item.estado_preparacion for item in items]

    if rules.pedido_entregado(estados):
        return _resultado(venta, estados, ya_entregado=True)
    if not rules.pedido_entregable(estados):
        raise ReglaNegocio(
            "el pedido no está listo: todos los ítems deben estar en `listo`"
        )

    for item in items:
        item.estado_preparacion = "entregado"

    event_bus.publish(
        "sales.venta_entregada",
        {
            "venta_id": str(venta.id),
            "sucursal_id": str(venta.sucursal_id),
            "modalidad": venta.modalidad,
            "cliente_id": str(venta.cliente_id) if venta.cliente_id else None,
            "repartidor_externo_plataforma": venta.repartidor_externo_plataforma,
            "entregado_por": str(entregado_por),
        },
    )
    return _resultado(venta, ["entregado"] * len(items), ya_entregado=False)


def _resultado(venta: Venta, estados: list[str], *, ya_entregado: bool) -> dict:
    return {
        "venta_id": str(venta.id),
        "numero_orden": venta.numero_orden,
        "modalidad": venta.modalidad,
        "estado_pedido": rules.estado_pedido(estados),
        "ya_entregado": ya_entregado,
    }
