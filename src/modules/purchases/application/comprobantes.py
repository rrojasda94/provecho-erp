"""Conformidad del comprobante recibido (RN-CMP-005): sustento de la compra
y disparador del pago. Compras sustenta, Contabilidad ejecuta — Compras
nunca paga (RN-CMP-014). `Comprobante` es transversal (`src/shared/models`),
no domicilia en `purchases`."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.purchases.application.errors import Conflicto, NoEncontrado
from src.modules.purchases.domain import rules
from src.modules.purchases.infrastructure.repositories import (
    OrdenCompraRepo,
    ProveedorRepo,
    RecepcionCompraRepo,
)
from src.shared.models import Comprobante


def dar_conformidad_comprobante(
    session: Session,
    orden_compra_id: uuid.UUID,
    *,
    idempotency_key: str,
    tipo: str,
    serie: str,
    correlativo: int,
    sustento: str,
) -> Comprobante:
    orden = OrdenCompraRepo(session).get(orden_compra_id)
    if orden is None:
        raise NoEncontrado("orden de compra no encontrada")
    if not rules.puede_dar_conformidad(orden.estado):
        raise Conflicto(
            f"la OC está {orden.estado}; requiere recepción registrada para dar conformidad"
        )

    existente = session.scalar(
        select(Comprobante).where(Comprobante.idempotency_key == idempotency_key)
    )
    if existente is not None:
        return existente

    proveedor = ProveedorRepo(session).get(orden.proveedor_id)

    comprobante = Comprobante(
        empresa_id=proveedor.empresa_id,
        compra_id=orden.id,
        direccion="recibido",
        tipo=tipo,
        serie=serie,
        correlativo=correlativo,
        sustento=sustento,
        idempotency_key=idempotency_key,
    )
    session.add(comprobante)
    session.flush()

    recepcion = RecepcionCompraRepo(session).ultima_de_orden(orden.id)
    if recepcion is not None and recepcion.comprobante_id is None:
        recepcion.comprobante_id = comprobante.id

    event_bus.publish(
        "purchases.comprobante_conforme",
        {
            "comprobante_id": str(comprobante.id),
            "orden_compra_id": str(orden.id),
            "proveedor_id": str(proveedor.id),
            "empresa_id": str(proveedor.empresa_id),
            "condicion_pago": proveedor.condicion_pago,
            "sujeto_spot": proveedor.sujeto_spot,
            "porcentaje_deteccion": (
                str(proveedor.porcentaje_deteccion)
                if proveedor.porcentaje_deteccion is not None
                else None
            ),
            "monto": str(orden.total),
        },
    )
    return comprobante
