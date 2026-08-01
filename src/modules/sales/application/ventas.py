"""Casos de uso de venta: crear (= confirmar orden), cobrar, anular.

Una venta creada ya ES una Orden de Pedido (estado `orden`) y publica
`sales.venta_confirmada` — el carrito previo vive en el cliente (PDV/kiosk),
no en el servidor.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.sales.application import comprobantes, precios
from src.modules.sales.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import Pago, Venta, VentaItem
from src.modules.sales.infrastructure.repositories import (
    MedioPagoRepo,
    PagoRepo,
    ProductoComercialRepo,
    VentaRepo,
)
from src.shared.models import Comprobante


def _armar_item(
    session: Session,
    it: dict,
    *,
    productos: ProductoComercialRepo,
    sucursal_id: uuid.UUID,
    canal: str,
    modalidad: str,
    dia: date,
) -> tuple[VentaItem, dict]:
    """Valida un ítem del request y le resuelve el precio. Devuelve la fila y
    el detalle que viaja en `sales.venta_confirmada` para que inventory
    descuente."""
    prod = productos.get(it["producto_comercial_id"])
    if prod is None or not prod.activo:
        raise NoEncontrado(
            f"producto comercial {it['producto_comercial_id']} no encontrado"
        )
    cantidad = Decimal(str(it["cantidad"]))
    if cantidad <= 0:
        raise ReglaNegocio("cantidad de ítem debe ser > 0")
    if it.get("precio_unitario") is None:
        precio_unitario = precios.resolver_precio(
            session,
            producto=prod,
            sucursal_id=sucursal_id,
            canal=canal,
            modalidad=modalidad,
            fecha=dia,
        )
    else:
        precio_unitario = Decimal(str(it["precio_unitario"]))
    fila = VentaItem(
        producto_comercial_id=prod.id,
        cantidad=cantidad,
        precio_unitario=precio_unitario,
        # Los descuentos salen de listas promocionales, no del cliente
        # (RN-PRC-003); en replay viaja el que ya se aplicó.
        descuento=Decimal(str(it.get("descuento") or 0)),
    )
    # Empaque se descuenta solo en las modalidades configuradas (RN-EMP-003).
    con_empaque = bool(prod.empaque_id and modalidad in (prod.modalidades_empaque or []))
    detalle = {
        "receta_id": str(prod.receta_id),
        "cantidad": str(cantidad),
        "empaque_articulo_id": str(prod.empaque_id) if con_empaque else None,
    }
    return fila, detalle


def crear_venta(
    session: Session,
    *,
    sucursal_id: uuid.UUID,
    punto_venta_id: uuid.UUID,
    canal: str,
    modalidad: str,
    usuario_id: uuid.UUID,
    idempotency_key: str,
    items: list[dict],  # [{producto_comercial_id, cantidad}]
    cliente_id: uuid.UUID | None = None,
    referencia_atencion: str | None = None,
    id: uuid.UUID | None = None,
    fecha_orden: date | None = None,
    numero_orden: int | None = None,
) -> Venta:
    """`id`, `fecha_orden` y `numero_orden` los fija el cliente solo cuando
    la venta ya ocurrió en otro lado y se está reproduciendo acá: es el
    caso del hub de sucursal sincronizando lo que vendió durante un corte
    (ADR-009). Sin ellos la nube y el hub generarían identificadores
    distintos para la misma venta, y el número de orden que vio el cliente
    en su comanda no sería el de la nube.

    El **precio lo fija el servidor** contra `lista_precio` (RN-PRC-003): el
    PDV manda producto y cantidad, nunca el monto. `precio_unitario` en un
    ítem solo lo acepta ese mismo camino de replay — una venta que ya se
    cobró conserva el precio al que se cobró, aunque la promoción haya
    vencido entre el corte y la sincronización.
    """
    if canal not in rules.CANALES:
        raise ReglaNegocio(f"canal inválido: {canal}")
    if modalidad not in rules.MODALIDADES:
        raise ReglaNegocio(f"modalidad inválida: {modalidad}")
    if not items:
        raise ReglaNegocio("una venta requiere al menos un ítem")

    repo = VentaRepo(session)
    # Idempotencia: reintento del mismo request devuelve la venta existente.
    existente = repo.get_by_idempotency(idempotency_key)
    if existente is not None:
        return existente
    if id is not None and repo.get(id) is not None:
        raise Conflicto(f"ya existe una venta con id {id} y otra idempotency_key")

    dia = fecha_orden or date.today()
    productos = ProductoComercialRepo(session)
    armados = [
        _armar_item(
            session, it, productos=productos, sucursal_id=sucursal_id,
            canal=canal, modalidad=modalidad, dia=dia,
        )
        for it in items
    ]
    filas = [fila for fila, _ in armados]
    detalle_evento = [detalle for _, detalle in armados]

    venta = Venta(
        id=id or uuid.uuid4(),
        sucursal_id=sucursal_id,
        fecha_orden=dia,
        numero_orden=numero_orden or repo.siguiente_numero_orden(sucursal_id, dia),
        punto_venta_id=punto_venta_id,
        canal=canal,
        modalidad=modalidad,
        cliente_id=cliente_id,
        usuario_id=usuario_id,
        estado="orden",
        total=rules.total_venta(
            [(f.cantidad, f.precio_unitario, f.descuento) for f in filas]
        ),
        idempotency_key=idempotency_key,
        referencia_atencion=referencia_atencion,
    )
    # ponytail: correlativo max+1; el UNIQUE (sucursal, fecha, numero) corta
    # la carrera — si dos cajas chocan, el cliente reintenta con la misma
    # idempotency_key. Secuencia por sucursal si el volumen lo pide.
    repo.add(venta)
    for fila in filas:
        fila.venta_id = venta.id
        session.add(fila)
    session.flush()

    event_bus.publish(
        "sales.venta_confirmada",
        {
            "venta_id": str(venta.id),
            "sucursal_id": str(sucursal_id),
            "items": detalle_evento,
            "total": str(venta.total),
        },
        session=session,
    )
    return venta


def registrar_pago(
    session: Session,
    *,
    venta_id: uuid.UUID,
    medio_pago_id: uuid.UUID,
    monto: Decimal,
    idempotency_key: str,
    referencia_externa: str | None = None,
    id: uuid.UUID | None = None,
) -> tuple[Pago, Venta, Comprobante | None]:
    """El pago nace `confirmado` (PDV presencial). Pasarela con webhook de
    confirmación async = slice Izipay posterior.

    Al cubrirse el total se crea el `comprobante` en estado `pendiente`; el
    envío a SUNAT lo hace la cola (el tercer valor devuelto es lo que el
    router encola tras el commit).

    `id` explícito: mismo motivo que en `crear_venta` — un cobro hecho
    offline conserva su identificador al reproducirse en la nube (ADR-009).
    """
    repo = PagoRepo(session)
    existente = repo.get_by_idempotency(idempotency_key)
    venta = VentaRepo(session).get(venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    if existente is not None:
        return existente, venta, None
    if id is not None and repo.get(id) is not None:
        raise Conflicto(f"ya existe un pago con id {id} y otra idempotency_key")

    if venta.estado not in ("orden",):
        raise Conflicto(f"la venta está {venta.estado}; no admite pagos")
    if MedioPagoRepo(session).get(medio_pago_id) is None:
        raise NoEncontrado("medio de pago no encontrado")
    if monto <= 0:
        raise ReglaNegocio("el monto debe ser > 0")

    confirmados = repo.confirmados(venta_id)
    if sum(confirmados, Decimal(0)) + monto > venta.total:
        raise ReglaNegocio("el pago excede el saldo de la venta")

    pago = repo.add(
        Pago(
            id=id or uuid.uuid4(),
            venta_id=venta_id,
            medio_pago_id=medio_pago_id,
            monto=monto,
            idempotency_key=idempotency_key,
            referencia_externa=referencia_externa,
            estado="confirmado",
        )
    )
    comprobante = None
    if rules.pagos_cubren_total(confirmados + [monto], venta.total):
        venta.estado = "pagada"
        event_bus.publish(
            "sales.venta_pagada",
            {"venta_id": str(venta.id), "total": str(venta.total)},
            session=session,
        )
        comprobante = comprobantes.crear_comprobante_pendiente(session, venta)
    return pago, venta, comprobante


def anular_venta(session: Session, venta_id: uuid.UUID, usuario_id: uuid.UUID) -> Venta:
    venta = VentaRepo(session).get(venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    if not rules.puede_anular(venta.estado):
        raise Conflicto(
            f"venta {venta.estado}: anulación post-pago requiere nota de crédito"
        )
    venta.estado = "anulada"
    productos = ProductoComercialRepo(session)
    items = []
    for it in VentaRepo(session).items(venta_id):
        prod = productos.get(it.producto_comercial_id)
        items.append({"receta_id": str(prod.receta_id), "cantidad": str(it.cantidad)})
    event_bus.publish(
        "sales.venta_anulada",
        {
            "venta_id": str(venta.id),
            "sucursal_id": str(venta.sucursal_id),
            "usuario_id": str(usuario_id),
            "items": items,
        },
        session=session,
    )
    return venta
