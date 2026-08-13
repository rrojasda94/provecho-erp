"""Casos de uso del KDS: pantallas configurables, cadena de estaciones,
cola, avance de ítems (bump), avance real del pedido y comanda imprimible.

El estado de preparación vive en `venta_item` — fuente única. Cada
pantalla es solo un FILTRO sobre ese estado, por eso el avance que
muestra cualquier pantalla siempre es el real. El frontend refresca por
polling; push (Redis/WebSocket) queda para el slice de tiempo real.

La cadena (armado → horno → despacho) es `kds_pantalla.orden` +
`venta_item.etapa_kds`, y se resuelve entera en `_estacion()`: la misma
función dice qué estación le toca a una línea y cuál es la siguiente
(ADR-044). Un solo lugar, porque cola y avance que discrepen dejarían
líneas invisibles en cocina.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.inventory.application.queries_publicas import nombres_de_articulos
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
    orden: int = 0,
) -> KdsPantalla:
    if tipo not in TIPOS_PANTALLA:
        raise ReglaNegocio(f"tipo de pantalla inválido: {tipo}")
    _validar_orden(orden)
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
        categoria_ids=categoria_ids, orden=orden,
    )
    session.add(pantalla)
    session.flush()
    return pantalla


def _validar_orden(orden: int) -> None:
    """La cadena se recorre hacia adelante y `etapa_kds` nace en 0: un orden
    negativo sería un eslabón al que nunca se llega."""
    if orden < 0:
        raise ReglaNegocio("el orden de la estación no puede ser negativo")


def editar_pantalla(session: Session, pantalla_id: uuid.UUID, **campos) -> KdsPantalla:
    pantalla = session.get(KdsPantalla, pantalla_id)
    if pantalla is None:
        raise NoEncontrado("pantalla no encontrada")
    for campo in ("nombre", "tipo", "categoria_ids", "activo", "orden"):
        if campo in campos and campos[campo] is not None:
            if campo == "tipo" and campos[campo] not in TIPOS_PANTALLA:
                raise ReglaNegocio(f"tipo de pantalla inválido: {campos[campo]}")
            if campo == "orden":
                _validar_orden(campos[campo])
            setattr(pantalla, campo, campos[campo])
    return pantalla


def listar_pantallas(
    session: Session, sucursal_id: uuid.UUID | None = None
) -> list[KdsPantalla]:
    q = select(KdsPantalla).where(KdsPantalla.deleted_at.is_(None))
    if sucursal_id is not None:
        q = q.where(KdsPantalla.sucursal_id == sucursal_id)
    # Ordenadas por la cadena: la lista de estaciones ES el recorrido del
    # pedido, y mostrarla alfabética lo escondería.
    return list(session.scalars(q.order_by(KdsPantalla.orden, KdsPantalla.nombre)))


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


def _restas_por_item(session: Session, pares: list[tuple]) -> dict[uuid.UUID, list[str]]:
    """`venta_item_id` → ["Cebolla", "Aceituna"]: lo que el plato NO lleva.

    Cocina necesita el nombre, no el id. `sales` guarda ids de artículo y no
    puede leer `articulo`, así que los nombres salen del contrato público de
    `inventory`. Un artículo borrado deja "—": el pedido igual tiene que
    poder imprimirse.

    ponytail: una consulta por venta (la cola las recorre en bucle). Con una
    cola de decenas de pedidos no se nota; si el KDS crece a cientos, esto
    se agrupa en una sola consulta por cola.
    """
    ids = {
        uuid.UUID(a) for it, _ in pares for a in (it.sin_articulo_ids or [])
    }
    if not ids:
        return {}
    nombres = nombres_de_articulos(session, ids)
    return {
        it.id: [nombres.get(uuid.UUID(a), "—") for a in it.sin_articulo_ids]
        for it, _ in pares
        if it.sin_articulo_ids
    }


def _pertenece(pantalla: KdsPantalla, producto: ProductoComercial) -> bool:
    """¿La pantalla atiende la categoría de este producto? NULL/[] = todas."""
    if not pantalla.categoria_ids:
        return True
    return str(producto.categoria_id) in pantalla.categoria_ids


def _cadena(session: Session, sucursal_id: uuid.UUID) -> list[KdsPantalla]:
    """Estaciones de preparación activas de la sucursal, en orden de recorrido.

    Despacho queda fuera a propósito: no es un eslabón que la línea tenga
    que atravesar, es lo que mira el pedido cuando ya no le queda ninguno.
    """
    return list(
        session.scalars(
            select(KdsPantalla)
            .where(
                KdsPantalla.sucursal_id == sucursal_id,
                KdsPantalla.tipo == "preparacion",
                KdsPantalla.activo.is_(True),
                KdsPantalla.deleted_at.is_(None),
            )
            .order_by(KdsPantalla.orden, KdsPantalla.nombre)
        )
    )


def _estacion(
    cadena: list[KdsPantalla], producto: ProductoComercial, desde: int
) -> KdsPantalla | None:
    """Primera estación con `orden >= desde` que atiende este producto.

    Es `>=` y no `==` a propósito: si el eslabón exacto de la línea ya no
    existe —lo desactivaron, le cambiaron las categorías—, la línea cae a
    la siguiente estación que sí la acepte en vez de quedar invisible.
    `None` = ya no queda cadena por delante: la línea está lista.
    """
    for pantalla in cadena:
        if pantalla.orden >= desde and _pertenece(pantalla, producto):
            return pantalla
    return None


def _estacion_de(
    cadena: list[KdsPantalla], item: VentaItem, producto: ProductoComercial
) -> KdsPantalla | None:
    """Estación que le toca AHORA a la línea. `None` = ya terminó cocina."""
    if item.estado_preparacion in ("listo", "entregado"):
        return None
    return _estacion(cadena, producto, item.etapa_kds)


def _item_a_dict(
    item: VentaItem,
    producto: ProductoComercial,
    restas: dict[uuid.UUID, list[str]],
    estacion: KdsPantalla | None,
) -> dict:
    return {
        "venta_item_id": str(item.id),
        "producto": producto.nombre,
        "cantidad": str(item.cantidad),
        "estado": item.estado_preparacion,
        "sin": restas.get(item.id, []),
        "etapa_kds": item.etapa_kds,
        # Dónde está la línea ahora mismo. Es lo que despacho necesita para
        # saber si el pedido espera por el horno o por la barra; `None` = ya
        # no espera por nadie.
        "estacion": estacion.nombre if estacion else None,
    }


def cola_pantalla(session: Session, pantalla_id: uuid.UUID) -> list[dict]:
    """Pedidos activos de la sucursal, con los ítems que competen a la
    pantalla y el avance REAL del pedido completo (todas las categorías).
    """
    pantalla = session.get(KdsPantalla, pantalla_id)
    if pantalla is None or pantalla.deleted_at is not None:
        raise NoEncontrado("pantalla no encontrada")
    cadena = _cadena(session, pantalla.sucursal_id)

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
        restas = _restas_por_item(session, pares)
        mios, pendiente_aqui = _items_de_pantalla(pantalla, cadena, pares, restas)
        if pantalla.tipo == "preparacion":
            # La estación ve TODOS sus ítems, incluidos los que ya tachó: el
            # ítem tachado tiene que seguir a la vista de quien lo tachó. El
            # pedido desaparece de esta cola recién cuando la estación
            # terminó todo lo suyo — no ítem por ítem.
            if not mios or not pendiente_aqui:
                continue
        elif not any(e == "listo" for e in estados_todos):
            # Despacho: muestra pedidos con algo listo o todo listo.
            continue
        cola.append(
            {
                "venta_id": str(venta.id),
                "numero_orden": venta.numero_orden,
                "referencia_atencion": venta.referencia_atencion,
                "modalidad": venta.modalidad,
                "canal": venta.canal,
                # La cocina tiene que saber que está preparando comida del
                # personal: cambia la prioridad frente a un pedido de cliente.
                "tipo": venta.tipo,
                "consumo_motivo": venta.consumo_motivo,
                "estado_pedido": rules.estado_pedido(estados_todos),
                "items": mios,
            }
        )
    return cola


def _items_de_pantalla(
    pantalla: KdsPantalla,
    cadena: list[KdsPantalla],
    pares: list[tuple],
    restas: dict[uuid.UUID, list[str]],
) -> tuple[list[dict], bool]:
    """Ítems que le competen a la pantalla, y si le queda algo por hacer.

    Una estación ve todos los de sus categorías, incluidos los que ya mandó
    al eslabón siguiente: el ítem tachado tiene que seguir a la vista de
    quien lo tachó, y `estacion` dice a dónde se fue. Lo que saca al pedido
    de esta cola no es que la línea avance, es que a la estación no le
    quede nada pendiente. Despacho ve el pedido completo.
    """
    if pantalla.tipo != "preparacion":
        return (
            [
                _item_a_dict(it, prod, restas, _estacion_de(cadena, it, prod))
                for it, prod in pares
            ],
            True,
        )
    mios, pendiente = [], False
    for it, prod in pares:
        if not _pertenece(pantalla, prod):
            continue
        estacion = _estacion_de(cadena, it, prod)
        if estacion is not None and estacion.orden == pantalla.orden:
            pendiente = True
        mios.append(_item_a_dict(it, prod, restas, estacion))
    return mios, pendiente


def avanzar_item(
    session: Session, venta_item_id: uuid.UUID, nuevo_estado: str
) -> VentaItem:
    item = session.get(VentaItem, venta_item_id)
    if item is None:
        raise NoEncontrado("ítem de venta no encontrado")
    venta = session.get(Venta, item.venta_id)
    if venta.estado == "anulada":
        raise Conflicto("la venta está anulada")
    if nuevo_estado == "entregado":
        # La entrega cierra el pedido completo y exige su propio permiso
        # (RN-CUP-005/006) — no se marca ítem por ítem desde cocina.
        raise ReglaNegocio(
            "la entrega se registra en POST /sales/ventas/{venta_id}/entrega"
        )
    if not rules.transicion_preparacion_valida(item.estado_preparacion, nuevo_estado):
        raise ReglaNegocio(
            f"transición inválida: {item.estado_preparacion} → {nuevo_estado}"
        )
    if nuevo_estado == "listo" and _pasar_a_la_siguiente(session, item, venta):
        # Tachar en una estación intermedia no es "listo": es "listo ACÁ".
        # La línea sigue en preparación, ahora en el eslabón siguiente.
        return item
    item.estado_preparacion = nuevo_estado

    estados = [
        it.estado_preparacion
        for it, _ in _items_de_venta(session, item.venta_id)
    ]
    if all(e in ("listo", "entregado") for e in estados):
        event_bus.publish(
            "sales.pedido_listo",
            {"venta_id": str(item.venta_id)},
            session=session,
        )
    return item


def _pasar_a_la_siguiente(session: Session, item: VentaItem, venta: Venta) -> bool:
    """Manda la línea al eslabón siguiente. `False` = no quedaba ninguno.

    El siguiente se busca desde la estación que la línea tiene AHORA y no
    desde `etapa_kds + 1`: si el eslabón exacto ya no existe, `etapa_kds`
    apunta más atrás que la estación real y sumarle uno devolvería la misma
    estación — la línea se quedaría rebotando ahí para siempre.
    """
    producto = session.get(ProductoComercial, item.producto_comercial_id)
    cadena = _cadena(session, venta.sucursal_id)
    actual = _estacion(cadena, producto, item.etapa_kds)
    if actual is None:
        return False
    siguiente = _estacion(cadena, producto, actual.orden + 1)
    if siguiente is None:
        return False
    item.etapa_kds = siguiente.orden
    return True


def avance_venta(session: Session, venta_id: uuid.UUID) -> dict:
    venta = session.get(Venta, venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    pares = _items_de_venta(session, venta_id)
    estados = [it.estado_preparacion for it, _ in pares]
    restas = _restas_por_item(session, pares)
    cadena = _cadena(session, venta.sucursal_id)
    return {
        "venta_id": str(venta_id),
        "numero_orden": venta.numero_orden,
        "referencia_atencion": venta.referencia_atencion,
        "estado_pedido": rules.estado_pedido(estados),
        "items": [
            _item_a_dict(it, prod, restas, _estacion_de(cadena, it, prod))
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
    if rules.es_consumo_personal(venta.tipo):
        lineas.append("** CONSUMO PERSONAL **".center(ANCHO_COMANDA))
        lineas.append(f"({venta.consumo_motivo})".center(ANCHO_COMANDA))
        lineas.append("-" * ANCHO_COMANDA)
    if reimpresion:
        lineas.append("** REIMPRESION **".center(ANCHO_COMANDA))
        lineas.append("-" * ANCHO_COMANDA)
    restas = _restas_por_item(session, pares)
    for it, prod in pares:
        cant = f"{it.cantidad.normalize()}x"
        lineas.append(f"{cant} {prod.nombre}"[:ANCHO_COMANDA])
        # Sangrada y en mayúsculas: en la cocina la comanda se lee de reojo,
        # y una resta que pasa desapercibida sale como plato rehecho.
        for nombre in restas.get(it.id, []):
            lineas.append(f"   SIN {nombre.upper()}"[:ANCHO_COMANDA])
    lineas.append("*" * ANCHO_COMANDA)
    return {
        "venta_id": str(venta_id),
        "numero_orden": venta.numero_orden,
        "reimpresion": reimpresion,
        "impresa_veces": venta.comanda_impresa_veces,
        "texto": "\n".join(lineas),
    }
