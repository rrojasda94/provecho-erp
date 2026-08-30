"""Conformidad del comprobante recibido (RN-CMP-005): sustento de la compra
y disparador del pago. Compras sustenta, Contabilidad ejecuta — Compras
nunca paga (RN-CMP-014). `Comprobante` es transversal (`src/shared/models`),
no domicilia en `purchases`."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.purchases.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.purchases.domain import rules
from src.modules.purchases.infrastructure.models import OrdenCompra, Proveedor
from src.modules.purchases.infrastructure.repositories import (
    OrdenCompraRepo,
    ProveedorRepo,
    RecepcionCompraRepo,
)
from src.shared import fechas
from src.shared.models import Comprobante


def comprobantes_de_orden(
    session: Session, orden_compra_id: uuid.UUID
) -> list[Comprobante]:
    """Qué factura(s) sustentan esta OC. La ficha lo necesita para saber si
    ya se dio conformidad y con qué documento."""
    return list(
        session.scalars(
            select(Comprobante)
            .where(Comprobante.compra_id == orden_compra_id)
            .order_by(Comprobante.created_at)
        )
    )


def q_comprobantes_recibidos(
    empresa_id: uuid.UUID | None,
    *,
    desde: date | None = None,
    hasta: date | None = None,
    proveedor_id: uuid.UUID | None = None,
    tipo: str | None = None,
):
    """El registro de compras: los comprobantes que la empresa recibió.

    Devuelve la consulta sin ejecutar para que el router la pagine (ADR-026).

    El rango de fechas cae a `created_at` cuando `fecha_emision` está vacía —
    lo registrado antes de que la columna existiera no la tiene, y dejarlo
    fuera de todo filtro por fecha lo volvería invisible en la pantalla.
    """
    q = select(Comprobante).where(Comprobante.direccion == "recibido")
    if empresa_id is not None:
        q = q.where(Comprobante.empresa_id == empresa_id)
    if tipo is not None:
        q = q.where(Comprobante.tipo == tipo)
    if proveedor_id is not None:
        # `compra_id` no tiene FK (apunta a otro módulo), así que el join va
        # explícito.
        q = q.join(OrdenCompra, OrdenCompra.id == Comprobante.compra_id).where(
            OrdenCompra.proveedor_id == proveedor_id
        )
    fecha = func.coalesce(Comprobante.fecha_emision, func.date(Comprobante.created_at))
    if desde is not None:
        q = q.where(fecha >= desde)
    if hasta is not None:
        q = q.where(fecha <= hasta)
    # Lo más reciente primero: un registro de compras se lee por el último
    # documento que entró, no por el primero.
    return q.order_by(Comprobante.created_at.desc(), Comprobante.id.desc())


def datos_de_ordenes(
    session: Session, orden_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict]:
    """Proveedor y total de cada OC nombrada, en una consulta.

    Se compone **después** de paginar y no con un join a la consulta: un join
    cambiaría el conteo de `paginar` y ordenar por columnas de la otra tabla.
    """
    ids = {i for i in orden_ids if i is not None}
    if not ids:
        return {}
    filas = session.execute(
        select(OrdenCompra.id, OrdenCompra.total, OrdenCompra.proveedor_id, Proveedor)
        .join(Proveedor, Proveedor.id == OrdenCompra.proveedor_id)
        .where(OrdenCompra.id.in_(ids))
    ).all()
    return {
        orden_id: {
            "proveedor_id": proveedor_id,
            "proveedor": proveedor.razon_social,
            "total_orden": total,
        }
        for orden_id, total, proveedor_id, proveedor in filas
    }


def _exigir_no_duplicado(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    emisor_num_doc: str | None,
    serie: str,
    correlativo: int,
) -> None:
    """El mismo documento del mismo proveedor no entra dos veces.

    El índice único ya lo impide, pero un `IntegrityError` sale como 500 y no
    dice cuál era el documento repetido. Esto es el mensaje; el índice sigue
    siendo la red que ataja la carrera entre dos usuarios simultáneos.
    """
    if emisor_num_doc is None:
        return
    ya = session.scalar(
        select(Comprobante).where(
            Comprobante.empresa_id == empresa_id,
            Comprobante.direccion == "recibido",
            Comprobante.emisor_num_doc == emisor_num_doc,
            Comprobante.serie == serie,
            Comprobante.correlativo == correlativo,
        )
    )
    if ya is not None:
        raise Conflicto(
            f"{serie}-{correlativo} de {emisor_num_doc} ya está registrado"
        )


def dar_conformidad_comprobante(
    session: Session,
    orden_compra_id: uuid.UUID,
    *,
    idempotency_key: str,
    tipo: str,
    serie: str,
    correlativo: int,
    sustento: str,
    gravado_igv: bool | None = None,
    emisor_num_doc: str | None = None,
    fecha_emision: date | None = None,
    total: Decimal | None = None,
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
    # El emisor es el proveedor de la OC salvo que el papel diga otra cosa.
    # Dejarlo vacío por omisión sería regalar la protección: la unicidad de un
    # documento recibido se calcula por emisor, y sin él no participa.
    emisor_num_doc = emisor_num_doc or proveedor.ruc

    if fecha_emision is not None and fecha_emision > fechas.hoy():
        raise ReglaNegocio("una factura no se emite mañana")

    _exigir_no_duplicado(
        session,
        empresa_id=proveedor.empresa_id,
        emisor_num_doc=emisor_num_doc,
        serie=serie,
        correlativo=correlativo,
    )

    comprobante = Comprobante(
        empresa_id=proveedor.empresa_id,
        compra_id=orden.id,
        direccion="recibido",
        tipo=tipo,
        serie=serie,
        correlativo=correlativo,
        sustento=sustento,
        idempotency_key=idempotency_key,
        gravado_igv=gravado_igv,
        emisor_num_doc=emisor_num_doc,
        fecha_emision=fecha_emision,
        total=total,
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
            # La base de lo recibido, que es lo que la plantilla del PCGE
            # espera (`monto_es="base"`). **No** el total facturado: apuntarlo
            # ahí duplicaría el IGV, que este mismo asiento agrega.
            "monto": str(orden.total),
            # El importe del papel, aditivo y todavía sin consumidor. Existe
            # para que la conciliación pueda comparar contra lo recibido el
            # día que se construya (deuda de `purchases`).
            "total_documento": str(total) if total is not None else None,
            # `accounting` lo necesita para el asiento del crédito fiscal:
            # la recepción asentó la compra sin IGV porque el comprobante
            # todavía no existía.
            "gravado_igv": gravado_igv,
        },
        session=session,
    )
    return comprobante
