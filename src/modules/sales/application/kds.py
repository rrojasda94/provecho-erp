"""Casos de uso del KDS: pantallas configurables, cola por categorías,
avance de ítems (bump), avance real del pedido y comanda imprimible.

El estado de preparación vive en `venta_item` — fuente única. Cada
pantalla es solo un FILTRO sobre ese estado, por eso el avance que
muestra cualquier pantalla siempre es el real. El frontend refresca por
polling; push (Redis/WebSocket) queda para el slice de tiempo real.
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
from src.modules.sales.infrastructure.models import (
    KdsPantalla,
    ProductoComercial,
    Venta,
    VentaItem,
)

TIPOS_PANTALLA = {"preparacion", "despacho"}


# --- Configuración de pantallas ----------------------------------------------
def crear_pantalla(
    session: Session,
    *,
    sucursal_id: uuid.UUID,
    nombre: str,
    tipo: str,
    categoria_ids: list[str] | None = None,
) -> KdsPantalla:
    if tipo not in TIPOS_PANTALLA:
        raise ReglaNegocio(f"tipo de pantalla inválido: {tipo}")
    existe = session.scalar(
        select(KdsPantalla).where(
            KdsPantalla.sucursal_id == sucursal_id,
            KdsPantalla.nombre == nombre,
            KdsPantalla.deleted_at.is_(None),
        )
    )
    if existe:
        raise Conflicto(f"pantalla '{nombre}' ya existe en la sucursal")
    pantalla = KdsPantalla(
        sucursal_id=sucursal_id, nombre=nombre, tipo=tipo,
        categoria_ids=categoria_ids,
    )
    session.add(pantalla)
    session.flush()
    return pantalla


def editar_pantalla(session: Session, pantalla_id: uuid.UUID, **campos) -> KdsPantalla:
    pantalla = session.get(KdsPantalla, pantalla_id)
    if pantalla is None:
        raise NoEncontrado("pantalla no encontrada")
    for campo in ("nombre", "tipo", "categoria_ids", "activo"):
        if campo in campos and campos[campo] is not None:
            if campo == "tipo" and campos[campo] not in TIPOS_PANTALLA:
                raise ReglaNegocio(f"tipo de pantalla inválido: {campos[campo]}")
            setattr(pantalla, campo, campos[campo])
    return pantalla


def listar_pantallas(
    session: Session, sucursal_id: uuid.UUID | None = None
) -> list[KdsPantalla]:
    q = select(KdsPantalla).where(KdsPantalla.deleted_at.is_(None))
    if sucursal_id is not None:
        q = q.where(KdsPantalla.sucursal_id == sucursal_id)
    return list(session.scalars(q.order_by(KdsPantalla.nombre)))


# --- Cola y avance ------------------------------------------------------------
def _items_de_venta(session: Session, venta_id: uuid.UUID) -> list[tuple]:
    """[(item, producto)] de una venta."""
    return list(
        session.execute(
            select(VentaItem, ProductoComercial)
            .join(
                ProductoComercial,
                ProductoComercial.id == VentaItem.producto_comercial_id,
            )
            .where(VentaItem.venta_id == venta_id)
        )
    )


def _pertenece(pantalla: KdsPantalla, producto: ProductoComercial) -> bool:
    """¿La pantalla atiende la categoría de este producto? NULL/[] = todas."""
    if not pantalla.categoria_ids:
        return True
    return str(producto.categoria_id) in pantalla.categoria_ids


def cola_pantalla(session: Session, pantalla_id: uuid.UUID) -> list[dict]:
    """Pedidos activos de la sucursal, con los ítems que competen a la
    pantalla y el avance REAL del pedido completo (todas las categorías).
    """
    pantalla = session.get(KdsPantalla, pantalla_id)
    if pantalla is None or pantalla.deleted_at is not None:
        raise NoEncontrado("pantalla no encontrada")

    ventas = session.scalars(
        select(Venta)
        .where(
            Venta.sucursal_id == pantalla.sucursal_id,
            Venta.estado.in_(("orden", "pagada")),
        )
        .order_by(Venta.fecha_orden, Venta.numero_orden)
    )

    cola = []
    for venta in ventas:
        pares = _items_de_venta(session, venta.id)
        estados_todos = [it.estado_preparacion for it, _ in pares]
        # Pedido cerrado en cocina: nada que mostrar.
        if estados_todos and all(e == "entregado" for e in estados_todos):
            continue
        mios = [
            {
                "venta_item_id": str(it.id),
                "producto": prod.nombre,
                "cantidad": str(it.cantidad),
                "estado": it.estado_preparacion,
            }
            for it, prod in pares
            if _pertenece(pantalla, prod)
        ]
        if pantalla.tipo == "preparacion":
            # Estación: solo ítems aún no listos de sus categorías.
            mios = [m for m in mios if m["estado"] in ("pendiente", "en_preparacion")]
            if not mios:
                continue
        else:
            # Despacho: muestra pedidos con algo listo o todo listo.
            if not any(e in ("listo",) for e in estados_todos):
                continue
        cola.append(
            {
                "venta_id": str(venta.id),
                "numero_orden": venta.numero_orden,
                "referencia_atencion": venta.referencia_atencion,
                "modalidad": venta.modalidad,
                "canal": venta.canal,
                "estado_pedido": rules.estado_pedido(estados_todos),
                "items": mios,
            }
        )
    return cola


def avanzar_item(
    session: Session, venta_item_id: uuid.UUID, nuevo_estado: str
) -> VentaItem:
    item = session.get(VentaItem, venta_item_id)
    if item is None:
        raise NoEncontrado("ítem de venta no encontrado")
    venta = session.get(Venta, item.venta_id)
    if venta.estado == "anulada":
        raise Conflicto("la venta está anulada")
    if not rules.transicion_preparacion_valida(item.estado_preparacion, nuevo_estado):
        raise ReglaNegocio(
            f"transición inválida: {item.estado_preparacion} → {nuevo_estado}"
        )
    item.estado_preparacion = nuevo_estado

    estados = [
        it.estado_preparacion
        for it, _ in _items_de_venta(session, item.venta_id)
    ]
    if all(e in ("listo", "entregado") for e in estados):
        event_bus.publish(
            "sales.pedido_listo", {"venta_id": str(item.venta_id)}
        )
    return item


def avance_venta(session: Session, venta_id: uuid.UUID) -> dict:
    venta = session.get(Venta, venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    pares = _items_de_venta(session, venta_id)
    estados = [it.estado_preparacion for it, _ in pares]
    return {
        "venta_id": str(venta_id),
        "numero_orden": venta.numero_orden,
        "referencia_atencion": venta.referencia_atencion,
        "estado_pedido": rules.estado_pedido(estados),
        "items": [
            {
                "venta_item_id": str(it.id),
                "producto": prod.nombre,
                "cantidad": str(it.cantidad),
                "estado": it.estado_preparacion,
            }
            for it, prod in pares
        ],
    }


# --- Comanda ------------------------------------------------------------------
ANCHO_COMANDA = 32  # impresora térmica 58 mm


def comanda(session: Session, venta_id: uuid.UUID) -> dict:
    """Texto plano listo para impresora térmica. Incrementa el contador —
    más de una impresión = reimpresión (auditable)."""
    venta = session.get(Venta, venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    pares = _items_de_venta(session, venta_id)

    venta.comanda_impresa_veces += 1
    reimpresion = venta.comanda_impresa_veces > 1

    lineas = [
        "*" * ANCHO_COMANDA,
        f"ORDEN #{venta.numero_orden}".center(ANCHO_COMANDA),
    ]
    if venta.referencia_atencion:
        lineas.append(venta.referencia_atencion.upper().center(ANCHO_COMANDA))
    lineas += [
        f"{venta.modalidad.upper()} / {venta.canal.upper()}".center(ANCHO_COMANDA),
        f"{venta.created_at:%d/%m/%Y %H:%M}".center(ANCHO_COMANDA),
        "*" * ANCHO_COMANDA,
    ]
    if reimpresion:
        lineas.append("** REIMPRESION **".center(ANCHO_COMANDA))
        lineas.append("-" * ANCHO_COMANDA)
    for it, prod in pares:
        cant = f"{it.cantidad.normalize()}x"
        lineas.append(f"{cant} {prod.nombre}"[:ANCHO_COMANDA])
    lineas.append("*" * ANCHO_COMANDA)
    return {
        "venta_id": str(venta_id),
        "numero_orden": venta.numero_orden,
        "reimpresion": reimpresion,
        "impresa_veces": venta.comanda_impresa_veces,
        "texto": "\n".join(lineas),
    }
