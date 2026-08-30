"""Casos de uso de orden de compra: crear (borrador) → emitir → recibir
(total/parcial) → anular.

Tipo `activo` queda declarado en el esquema pero fuera de este slice
(requiere `requerimiento_activo` con doble aprobación de área/gerencia —
deuda técnica, ver ROADMAP).
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.inventory.infrastructure.models import Articulo
from src.modules.purchases.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.purchases.domain import rules
from src.modules.purchases.infrastructure.models import (
    OrdenCompra,
    OrdenCompraItem,
    RecepcionCompra,
    RecepcionItem,
)
from src.modules.purchases.infrastructure.repositories import (
    OrdenCompraRepo,
    ProveedorRepo,
    RecepcionCompraRepo,
)
from src.modules.users.infrastructure.models import Almacen
from src.shared import aprobaciones, auditoria


def construir_items(session: Session, items: list[dict]) -> tuple[list[OrdenCompraItem], Decimal]:
    filas = []
    total = Decimal(0)
    for it in items:
        if session.get(Articulo, it["articulo_id"]) is None:
            raise NoEncontrado(f"artículo {it['articulo_id']} no encontrado")
        cantidad = Decimal(str(it["cantidad"]))
        costo_unitario = Decimal(str(it["costo_unitario"]))
        if cantidad <= 0:
            raise ReglaNegocio("cantidad de ítem debe ser > 0")
        if costo_unitario < 0:
            raise ReglaNegocio("costo_unitario no puede ser negativo")
        filas.append(
            OrdenCompraItem(
                articulo_id=it["articulo_id"],
                cantidad=cantidad,
                costo_unitario=costo_unitario,
            )
        )
        total += cantidad * costo_unitario
    return filas, total


def crear_orden_compra(
    session: Session,
    *,
    proveedor_id: uuid.UUID,
    almacen_destino_id: uuid.UUID,
    creado_por: uuid.UUID,
    idempotency_key: str,
    items: list[dict],  # [{articulo_id, cantidad, costo_unitario}]
    tipo: str = "insumo",
) -> OrdenCompra:
    if tipo != "insumo":
        raise ReglaNegocio("OC tipo 'activo' requiere requerimiento_activo — aún no soportado")
    if not items:
        raise ReglaNegocio("una OC requiere al menos un ítem")

    repo = OrdenCompraRepo(session)
    existente = repo.get_by_idempotency(idempotency_key)
    if existente is not None:
        return existente

    proveedor = ProveedorRepo(session).get(proveedor_id)
    if proveedor is None or not proveedor.activo:
        raise NoEncontrado(f"proveedor {proveedor_id} no encontrado")
    if session.get(Almacen, almacen_destino_id) is None:
        raise NoEncontrado(f"almacén {almacen_destino_id} no encontrado")

    filas, total = construir_items(session, items)

    orden = OrdenCompra(
        proveedor_id=proveedor_id,
        tipo=tipo,
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
    return orden


def editar_orden_compra(
    session: Session,
    orden_compra_id: uuid.UUID,
    *,
    items: list[dict],  # [{articulo_id, cantidad, costo_unitario}]
    actor_id: uuid.UUID,
) -> OrdenCompra:
    """Reemplaza los ítems de una OC — solo mientras está en `borrador`
    (RN: precio/cantidad son editables hasta emitir; desde `emitida` la OC
    es inmutable, sin excepción)."""
    orden = OrdenCompraRepo(session).get(orden_compra_id)
    if orden is None:
        raise NoEncontrado("orden de compra no encontrada")
    if orden.estado != "borrador":
        raise Conflicto(f"la OC está {orden.estado}; solo se edita en borrador")
    if not items:
        raise ReglaNegocio("una OC requiere al menos un ítem")

    filas, total = construir_items(session, items)

    proveedor = ProveedorRepo(session).get(orden.proveedor_id)
    total_antes = orden.total
    for item_previo in OrdenCompraRepo(session).items(orden.id):
        session.delete(item_previo)
    session.flush()
    for fila in filas:
        fila.orden_compra_id = orden.id
        session.add(fila)
    orden.total = total
    auditoria.registrar(
        session,
        usuario_id=actor_id,
        entidad="orden_compra",
        entidad_id=orden.id,
        accion="editar",
        datos_antes={"total": str(total_antes)},
        datos_despues={"total": str(total)},
        empresa_id=proveedor.empresa_id,
    )
    session.flush()
    return orden


def listar_ordenes_compra(
    session: Session, empresa_id: uuid.UUID | None = None
) -> list[OrdenCompra]:
    return OrdenCompraRepo(session).list(empresa_id)


def items_de_orden_compra(session: Session, orden_compra_id: uuid.UUID) -> list[OrdenCompraItem]:
    return OrdenCompraRepo(session).items(orden_compra_id)


def q_ordenes_compra(session: Session, empresa_id: uuid.UUID | None = None):
    """La consulta sin ejecutar, para que el router la pagine (ADR-026)."""
    return OrdenCompraRepo(session).q_list(empresa_id)


def recepciones_de_orden(session: Session, orden_compra_id: uuid.UUID) -> list[dict]:
    """Las recepciones de la OC con sus líneas, ya resueltas a `articulo_id`.

    Devuelve dicts y no ORM porque el artículo no está en `recepcion_item`
    sino en el ítem de la OC del que cuelga: armarlo en el router obligaría a
    que la API conociera ese join. Dos consultas, nunca una por recepción.
    """
    repo = RecepcionCompraRepo(session)
    recepciones = repo.de_orden(orden_compra_id)
    por_recepcion: dict[uuid.UUID, list[dict]] = {r.id: [] for r in recepciones}
    for item, articulo_id in repo.items_de([r.id for r in recepciones]):
        por_recepcion[item.recepcion_compra_id].append(
            {
                "id": item.id,
                "orden_compra_item_id": item.orden_compra_item_id,
                "articulo_id": articulo_id,
                "cantidad_recibida": item.cantidad_recibida,
                "costo_unitario": item.costo_unitario,
                "lote_codigo": item.lote_codigo,
                "fecha_vencimiento": item.fecha_vencimiento,
            }
        )
    return [
        {
            "id": r.id,
            "orden_compra_id": r.orden_compra_id,
            "recibido_por": r.recibido_por,
            "fecha": r.fecha,
            "comprobante_id": r.comprobante_id,
            "items": por_recepcion[r.id],
        }
        for r in recepciones
    ]


def emitir_orden_compra(
    session: Session,
    orden_compra_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    puede_aprobar_monto: bool,
    umbral_aprobacion: Decimal,
) -> OrdenCompra:
    orden = OrdenCompraRepo(session).get(orden_compra_id)
    if orden is None:
        raise NoEncontrado("orden de compra no encontrada")
    if not rules.puede_emitir(orden.estado):
        raise Conflicto(f"la OC está {orden.estado}; no admite emisión")
    proveedor = ProveedorRepo(session).get(orden.proveedor_id)
    umbral = aprobaciones.umbral_vigente(
        session, proveedor.empresa_id, "purchases", "oc_umbral", default=umbral_aprobacion
    )
    if rules.requiere_aprobacion(orden.total, umbral) and not puede_aprobar_monto:
        raise ReglaNegocio(
            f"total {orden.total} supera el umbral {umbral}; requiere permiso purchases.aprobar"
        )
    estado_previo = orden.estado
    orden.estado = "emitida"
    orden.emitido_por = actor_id
    orden.fecha_emision = datetime.now(UTC)
    auditoria.registrar(
        session,
        usuario_id=actor_id,
        entidad="orden_compra",
        entidad_id=orden.id,
        accion="emitir",
        datos_antes={"estado": estado_previo},
        datos_despues={
            "estado": "emitida",
            "total": str(orden.total),
            "umbral": str(umbral),
            "proveedor_id": str(orden.proveedor_id),
        },
        empresa_id=proveedor.empresa_id,
    )
    event_bus.publish(
        "purchases.oc_emitida",
        {
            "orden_compra_id": str(orden.id),
            "proveedor_id": str(orden.proveedor_id),
            "empresa_id": str(proveedor.empresa_id),
            "total": str(orden.total),
        },
        session=session,
    )
    return orden


def recibir_orden_compra(
    session: Session,
    orden_compra_id: uuid.UUID,
    *,
    recibido_por: uuid.UUID,
    idempotency_key: str,
    items: list[dict],  # [{orden_compra_item_id, cantidad_recibida, costo_unitario}]
) -> RecepcionCompra:
    orden = OrdenCompraRepo(session).get(orden_compra_id)
    if orden is None:
        raise NoEncontrado("orden de compra no encontrada")
    if not rules.puede_recibir(orden.estado):
        raise Conflicto(f"la OC está {orden.estado}; no admite recepción")
    if not items:
        raise ReglaNegocio("una recepción requiere al menos un ítem")

    recepcion_repo = RecepcionCompraRepo(session)
    existente = recepcion_repo.get_by_idempotency(idempotency_key)
    if existente is not None:
        return existente

    items_oc = {i.id: i for i in OrdenCompraRepo(session).items(orden.id)}
    recepcion = recepcion_repo.add(
        RecepcionCompra(
            orden_compra_id=orden.id,
            recibido_por=recibido_por,
            idempotency_key=idempotency_key,
        )
    )

    evento_items = []
    for it in items:
        oc_item = items_oc.get(it["orden_compra_item_id"])
        if oc_item is None:
            raise NoEncontrado(f"ítem {it['orden_compra_item_id']} no pertenece a esta OC")
        cantidad_recibida = Decimal(str(it["cantidad_recibida"]))
        if cantidad_recibida <= 0:
            raise ReglaNegocio("cantidad_recibida debe ser > 0")
        if oc_item.cantidad_recibida + cantidad_recibida > oc_item.cantidad:
            raise ReglaNegocio(
                f"ítem {oc_item.id}: recepción excede lo ordenado "
                f"({oc_item.cantidad_recibida + cantidad_recibida} > {oc_item.cantidad})"
            )
        costo_unitario_in = it.get("costo_unitario")
        costo_unitario = (
            Decimal(str(costo_unitario_in))
            if costo_unitario_in is not None
            else oc_item.costo_unitario
        )
        oc_item.cantidad_recibida += cantidad_recibida
        vencimiento = it.get("fecha_vencimiento")
        session.add(
            RecepcionItem(
                recepcion_compra_id=recepcion.id,
                orden_compra_item_id=oc_item.id,
                cantidad_recibida=cantidad_recibida,
                costo_unitario=costo_unitario,
                # El documento conserva lo que declaró el proveedor, no solo
                # el evento: si el listener de inventory falla, esto es lo
                # único que queda para reprocesar (RN-VNC-002).
                lote_codigo=it.get("lote_codigo"),
                fecha_vencimiento=(
                    date.fromisoformat(vencimiento) if isinstance(vencimiento, str) else vencimiento
                ),
            )
        )
        evento_items.append(
            {
                "articulo_id": str(oc_item.articulo_id),
                "cantidad": str(cantidad_recibida),
                "costo_unitario": str(costo_unitario),
                # Datos del lote recibido; inventory los ignora si el
                # artículo no controla lote (RN-VNC-002).
                "lote_codigo": it.get("lote_codigo"),
                "fecha_vencimiento": (
                    vencimiento.isoformat() if hasattr(vencimiento, "isoformat") else vencimiento
                ),
            }
        )

    orden.estado = rules.estado_tras_recepcion(
        [i.cantidad for i in items_oc.values()],
        [i.cantidad_recibida for i in items_oc.values()],
    )
    session.flush()

    event_bus.publish(
        "purchases.compra_recibida",
        {
            "orden_compra_id": str(orden.id),
            "almacen_destino_id": str(orden.almacen_destino_id),
            "items": evento_items,
        },
        session=session,
    )
    return recepcion


def anular_orden_compra(
    session: Session, orden_compra_id: uuid.UUID, actor_id: uuid.UUID
) -> OrdenCompra:
    orden = OrdenCompraRepo(session).get(orden_compra_id)
    if orden is None:
        raise NoEncontrado("orden de compra no encontrada")
    if not rules.puede_anular(orden.estado):
        raise Conflicto(f"OC {orden.estado}: con recepción registrada no admite anulación directa")
    orden.estado = "anulada"
    event_bus.publish(
        "purchases.oc_anulada",
        {"orden_compra_id": str(orden.id), "usuario_id": str(actor_id)},
        session=session,
    )
    return orden
