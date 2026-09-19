"""Checkout del sitio de marca (ADR-105): cotizar antes de confirmar,
confirmar el pedido, y publicar el evento que `sales` convierte en una
`Venta` real de canal `web`.

`storefront` nunca llama `sales.application.ventas.crear_venta` directamente
— eso sería cruzar el dominio de otro módulo. Publica `storefront.pedido_
web_confirmado` y `sales.application.listeners.on_pedido_web_confirmado`
hace la llamada real, con la respuesta llegando por `sales.pedido_web_
procesado` (`application/listeners.py::on_pedido_web_procesado` de este
módulo). El bus es síncrono en proceso (`core/events.py`): en la práctica,
para cuando `confirmar()` retorna, el pedido ya salió `confirmado` o
`fallido` — no hace falta que quien llama haga polling.
"""

import math
import secrets
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.events import event_bus
from src.modules.sales.application.queries_publicas import (
    carga_activa_por_sucursal,
    carta_publica,
    cotizar_delivery_publico,
    puntos_venta_web_de_sucursales,
    tiempos_preparacion,
)
from src.modules.storefront.application.errors import NoEncontrado, ReglaNegocio
from src.modules.storefront.domain import asignacion, carrito, opciones
from src.modules.storefront.infrastructure.models import (
    StorefrontPedido,
    StorefrontPedidoItem,
)
from src.modules.storefront.infrastructure.repositories import (
    CuentaRepo,
    PedidoItemRepo,
    PedidoRepo,
)
from src.modules.users.infrastructure.models import Sucursal
from src.shared import auditoria
from src.shared.integrations.izipay import izipay_disponible, pasarela_activa


@dataclass(frozen=True)
class Resolucion:
    sucursal_id: uuid.UUID
    punto_venta_id: uuid.UUID
    eta_min: int
    eta_max: int
    costo_delivery: Decimal | None = None
    distancia_km: Decimal | None = None


def _candidatas_activas(session: Session, marca_id: uuid.UUID) -> list[Sucursal]:
    return list(
        session.scalars(
            select(Sucursal).where(
                Sucursal.marca_id == marca_id,
                Sucursal.estado == "activa",
                Sucursal.deleted_at.is_(None),
            )
        )
    )


def _preparacion_min(session: Session, lineas: list[carrito.LineaCarrito]) -> int:
    """Lo que tarda el pedido en salir de cocina: el mayor tiempo entre sus
    productos. Un producto sin tiempo cargado cuenta como la base estándar
    (`STOREFRONT_ETA_BASE_MINUTOS`); uno con `0` sale al instante. Sin líneas
    —cotizar antes de tener carrito— es la base."""
    base = settings.storefront_eta_base_minutos
    if not lineas:
        return base
    tiempos = tiempos_preparacion(session, [linea.producto_comercial_id for linea in lineas])
    de_cada_linea = [tiempos.get(linea.producto_comercial_id) for linea in lineas]
    return max(base if t is None else t for t in de_cada_linea)


def _resolver_sucursal(
    session: Session,
    *,
    marca_id: uuid.UUID,
    modalidad: str,
    sucursal_id: uuid.UUID | None,
    destino_lat: Decimal | None,
    destino_lng: Decimal | None,
    destino_distrito: str | None,
    lineas: list[carrito.LineaCarrito] | None = None,
) -> Resolucion:
    """Recojo: el cliente ya eligió el local (`sucursal_id`), solo se valida
    y se calcula el ETA. Delivery: se elige el local automáticamente entre
    las candidatas dentro de radio (RN-WEB-010)."""
    candidatas = _candidatas_activas(session, marca_id)
    if not candidatas:
        raise ReglaNegocio("esta marca no tiene sucursales activas")

    puntos = puntos_venta_web_de_sucursales(session, [s.id for s in candidatas])
    elegibles = [
        s
        for s in candidatas
        if s.id in puntos and modalidad in puntos[s.id]["modalidades_habilitadas"]
    ]
    if not elegibles:
        raise ReglaNegocio(
            f"ninguna sucursal admite pedidos web en modalidad '{modalidad}' todavía"
        )

    cargas = carga_activa_por_sucursal(session, [s.id for s in elegibles])
    preparacion_min = _preparacion_min(session, lineas or [])

    if modalidad == "takeout":
        if sucursal_id is None:
            raise ReglaNegocio("elige un local para recojo")
        elegida = next((s for s in elegibles if s.id == sucursal_id), None)
        if elegida is None:
            raise NoEncontrado("esa sucursal no admite recojo por el sitio")
        carga = cargas.get(elegida.id, 0)
        eta_min, eta_max = asignacion.estimar_eta(
            carga,
            preparacion_min=preparacion_min,
            minutos_por_pedido=settings.storefront_eta_minutos_por_pedido,
        )
        return Resolucion(
            sucursal_id=elegida.id,
            punto_venta_id=puntos[elegida.id]["punto_venta_id"],
            eta_min=eta_min,
            eta_max=eta_max,
        )

    # Delivery: cada candidata se cotiza contra el destino y se descarta la
    # que quede fuera de radio o en zona restringida (mismo cálculo que usa
    # `crear_venta` al confirmar, vía `tarifa_delivery`).
    if destino_lat is None or destino_lng is None:
        raise ReglaNegocio("falta la ubicación de entrega")
    candidatas_cotizadas = []
    cotizaciones = {}
    for s in elegibles:
        cotizacion = cotizar_delivery_publico(
            session,
            sucursal_id=s.id,
            destino_lat=destino_lat,
            destino_lng=destino_lng,
            destino_distrito=destino_distrito,
        )
        if cotizacion["derivar_a_externo"]:
            continue
        cotizaciones[s.id] = cotizacion
        candidatas_cotizadas.append(
            asignacion.Candidata(
                sucursal_id=s.id,
                punto_venta_id=puntos[s.id]["punto_venta_id"],
                carga=cargas.get(s.id, 0),
                distancia_km=cotizacion["distancia_km"],
            )
        )
    elegida = asignacion.elegir(
        candidatas_cotizadas, saturacion=settings.storefront_saturacion_pedidos
    )
    if elegida is None:
        raise ReglaNegocio("fuera de cobertura de delivery")
    cotizacion = cotizaciones[elegida.sucursal_id]
    viaje_min = math.ceil(
        (cotizacion["distancia_km"] or Decimal(0)) * settings.storefront_eta_minutos_por_km
    )
    eta_min, eta_max = asignacion.estimar_eta(
        elegida.carga,
        preparacion_min=preparacion_min,
        minutos_por_pedido=settings.storefront_eta_minutos_por_pedido,
        viaje_min=viaje_min,
    )
    return Resolucion(
        sucursal_id=elegida.sucursal_id,
        punto_venta_id=elegida.punto_venta_id,
        eta_min=eta_min,
        eta_max=eta_max,
        costo_delivery=cotizacion["costo"],
        distancia_km=cotizacion["distancia_km"],
    )


def cotizar(
    session: Session,
    *,
    marca_id: uuid.UUID,
    modalidad: str,
    sucursal_id: uuid.UUID | None = None,
    destino_lat: Decimal | None = None,
    destino_lng: Decimal | None = None,
    destino_distrito: str | None = None,
    lineas: list[carrito.LineaCarrito] | None = None,
) -> dict:
    """Vista previa antes de confirmar: a qué sucursal iría el pedido, con
    qué ETA y (delivery) a qué costo — para mostrarlo en el checkout antes
    de que el cliente decida. Con `lineas` el ETA sale de lo que se pide."""
    r = _resolver_sucursal(
        session,
        marca_id=marca_id,
        modalidad=modalidad,
        sucursal_id=sucursal_id,
        destino_lat=destino_lat,
        destino_lng=destino_lng,
        destino_distrito=destino_distrito,
        lineas=lineas,
    )
    return {
        "sucursal_id": r.sucursal_id,
        "eta_min": r.eta_min,
        "eta_max": r.eta_max,
        "costo_delivery": r.costo_delivery,
        "distancia_km": r.distancia_km,
    }


@dataclass(frozen=True)
class NodoCarta:
    """Un producto vendible tal como lo muestra la carta pública: su precio,
    si está disponible y qué opciones (extras/sabores) admite."""

    precio: Decimal
    disponible: bool
    nombre: str
    opciones: opciones.OpcionesNodo


def _opciones_de(nodo: dict) -> opciones.OpcionesNodo:
    extras: dict[uuid.UUID, opciones.ExtraOfrecido] = {}
    grupos: dict[uuid.UUID, opciones.GrupoOfrecido] = {}
    for e in nodo.get("extras", []):
        extras[e["producto_comercial_id"]] = opciones.ExtraOfrecido(
            id=e["producto_comercial_id"],
            nombre=e["nombre"],
            precio=e["precio_unitario"],
            maximo=e["maximo"],
            grupo_id=e["grupo_id"],
        )
        if e["grupo_id"] is not None:
            grupos[e["grupo_id"]] = opciones.GrupoOfrecido(
                id=e["grupo_id"],
                nombre=e["grupo_nombre"],
                minimo=e["grupo_minimo"],
                maximo=e["grupo_maximo"],
            )
    atributos = tuple(
        opciones.AtributoOfrecido(
            nombre=a["nombre"],
            valores={
                v["id"]: opciones.ValorOfrecido(v["nombre"], v["precio_extra"])
                for v in a["valores"]
            },
        )
        for a in nodo.get("atributos", [])
    )
    exclusiones = frozenset(frozenset(par) for par in nodo.get("exclusiones", []))
    return opciones.OpcionesNodo(extras, grupos, atributos, exclusiones)


def _nodos_de_carta(
    session: Session, *, marca_id: uuid.UUID, sucursal_id: uuid.UUID, modalidad: str
) -> dict[uuid.UUID, NodoCarta]:
    """`{producto_comercial_id: NodoCarta}` de todo lo que aparece en la carta
    pública de esa sucursal — el mismo precio y las mismas opciones que ve el
    cliente al armar el carrito. Es lo que el pedido puede pedir: cualquier
    otra cosa se rechaza. `crear_venta` vuelve a fijar el precio server-side al
    confirmar (RN-PRC-003)."""
    items = carta_publica(
        session,
        marca_id=marca_id,
        sucursal_id=sucursal_id,
        canal=settings.storefront_canal,
        modalidad=modalidad,
    )
    nodos: dict[uuid.UUID, NodoCarta] = {}
    for item in items:
        for nodo in (item, *item.get("variantes", [])):
            nodos[nodo["producto_comercial_id"]] = NodoCarta(
                precio=nodo["precio_unitario"],
                disponible=not nodo["stock_bajo"],
                nombre=nodo["nombre"],
                opciones=_opciones_de(nodo),
            )
    return nodos


def _congelar_lineas(
    nodos: dict[uuid.UUID, NodoCarta], lineas: list[carrito.LineaCarrito]
) -> tuple[Decimal, list[dict]]:
    """Valida cada línea contra la carta y arma lo que se guarda: total (sin
    delivery) y las filas de `storefront_pedido_item`.

    El total de una línea es `(precio + recargo de sabores + extras) × cantidad`,
    lo mismo que suma `sales`: la línea a `precio + recargo` y cada extra como
    línea propia por `cantidad × cantidad del extra` (RN-COM-021, RN-COM-036).
    """
    total = Decimal("0")
    filas = []
    for linea in lineas:
        nodo = nodos.get(linea.producto_comercial_id)
        if nodo is None:
            raise NoEncontrado("un producto del carrito ya no está en la carta")
        if not nodo.disponible:
            raise ReglaNegocio(f"'{nodo.nombre}' no está disponible ahora mismo")
        try:
            elegido = opciones.evaluar(nodo.opciones, linea.extras, linea.valores)
        except ValueError as e:
            raise ReglaNegocio(f"'{nodo.nombre}': {e}") from e
        unitario = nodo.precio + elegido.recargo_valores
        total += (unitario + elegido.extras_por_unidad) * linea.cantidad
        filas.append(
            {
                "producto_comercial_id": linea.producto_comercial_id,
                "nombre_congelado": nodo.nombre,
                "cantidad": linea.cantidad,
                "precio_unitario_congelado": unitario,
                "extras": [
                    {
                        "producto_comercial_id": str(e.id),
                        "nombre": e.nombre,
                        "cantidad": c,
                        "precio": str(e.precio),
                    }
                    for e, c in elegido.extras
                ]
                or None,
                "valores": [
                    {"id": str(v_id), "nombre": v.nombre, "precio_extra": str(v.precio_extra)}
                    for v_id, v in elegido.valores
                ]
                or None,
            }
        )
    return total, filas


def confirmar(
    session: Session,
    *,
    marca_id: uuid.UUID,
    cuenta_id: uuid.UUID | None,
    nombre_contacto: str,
    telefono_contacto: str,
    email_contacto: str | None,
    modalidad: str,
    lineas: list[carrito.LineaCarrito],
    medio_pago: str,
    numero_documento: str | None,
    nombre_o_razon_social: str | None,
    idempotency_key: str,
    sucursal_id: uuid.UUID | None = None,
    direccion_entrega: str | None = None,
    ubicacion_place_id: str | None = None,
    ubicacion_lat: Decimal | None = None,
    ubicacion_lng: Decimal | None = None,
    ubicacion_plus_code: str | None = None,
    ubicacion_distrito: str | None = None,
) -> StorefrontPedido:
    repo = PedidoRepo(session)
    existente = repo.get_by_idempotency(idempotency_key)
    if existente is not None:
        return existente

    carrito.validar(lineas)
    _validar_medio_de_pago(medio_pago, con_cuenta=cuenta_id is not None)
    if modalidad == "delivery" and not direccion_entrega:
        raise ReglaNegocio("falta la dirección de entrega")

    r = _resolver_sucursal(
        session,
        marca_id=marca_id,
        modalidad=modalidad,
        sucursal_id=sucursal_id,
        destino_lat=ubicacion_lat,
        destino_lng=ubicacion_lng,
        destino_distrito=ubicacion_distrito,
        lineas=lineas,
    )

    nodos = _nodos_de_carta(
        session, marca_id=marca_id, sucursal_id=r.sucursal_id, modalidad=modalidad
    )
    total, items_congelados = _congelar_lineas(nodos, lineas)
    if r.costo_delivery:
        total += r.costo_delivery

    pedido = repo.add(
        StorefrontPedido(
            marca_id=marca_id,
            cuenta_id=cuenta_id,
            nombre_contacto=nombre_contacto,
            telefono_contacto=telefono_contacto,
            email_contacto=email_contacto,
            modalidad=modalidad,
            sucursal_id=r.sucursal_id,
            direccion_entrega=direccion_entrega,
            ubicacion_place_id=ubicacion_place_id,
            ubicacion_lat=ubicacion_lat,
            ubicacion_lng=ubicacion_lng,
            ubicacion_plus_code=ubicacion_plus_code,
            ubicacion_distrito=ubicacion_distrito,
            medio_pago=medio_pago,
            numero_documento=numero_documento,
            nombre_o_razon_social=nombre_o_razon_social,
            total_estimado=total,
            costo_delivery_estimado=r.costo_delivery,
            distancia_km_estimada=r.distancia_km,
            eta_min=r.eta_min,
            eta_max=r.eta_max,
            estado="pendiente",
            idempotency_key=idempotency_key,
            token_acceso=secrets.token_urlsafe(32),
        )
    )
    auditoria.registrar(
        session,
        usuario_id=None,
        entidad="storefront_pedido",
        entidad_id=pedido.id,
        accion="confirmar",
        datos_despues={
            "cuenta_id": str(cuenta_id) if cuenta_id else None,
            "modalidad": modalidad,
            "medio_pago": medio_pago,
            "total_estimado": str(total),
        },
    )
    item_repo = PedidoItemRepo(session)
    for fila in items_congelados:
        item_repo.add(StorefrontPedidoItem(pedido_id=pedido.id, **fila))

    if medio_pago == "izipay":
        _iniciar_cobro(session, pedido)
    else:
        publicar_confirmacion(session, pedido)
    session.commit()
    session.refresh(pedido)
    return pedido


def _validar_medio_de_pago(medio_pago: str, *, con_cuenta: bool) -> None:
    if medio_pago not in ("efectivo", "izipay"):
        raise ReglaNegocio(f"medio de pago inválido: {medio_pago}")
    if medio_pago == "efectivo" and not con_cuenta:
        # RN-WEB-013: sin cuenta no hay a quién reclamarle un pedido que no se
        # recoge o no se paga. Un invitado paga por adelantado con Izipay.
        raise ReglaNegocio(
            "Para pagar en efectivo necesitas una cuenta: regístrate o paga con Izipay."
        )
    if medio_pago == "izipay" and not izipay_disponible():
        raise ReglaNegocio("El pago con Izipay todavía no está disponible.")


def _iniciar_cobro(session: Session, pedido: StorefrontPedido) -> None:
    """Cobra ANTES de crear la venta: con la pasarela real el cliente paga en
    su pantalla y el resultado llega por webhook (`application/pagos.py`). El
    pedido queda pendiente y nada llega a cocina hasta que el pago se apruebe."""
    intento = pasarela_activa().crear_intento(
        monto=pedido.total_estimado,
        moneda="PEN",
        referencia=str(pedido.id),
        medio="izipay",
    )
    pedido.pago_id_externo = intento.id_externo
    pedido.pago_estado = intento.estado
    if intento.estado == "aprobado":
        publicar_confirmacion(session, pedido)


def publicar_confirmacion(session: Session, pedido: StorefrontPedido) -> None:
    """Publica `storefront.pedido_web_confirmado`, que `sales` convierte en
    una `Venta`. Sale de la fila ya guardada y no de lo que llegó en la
    petición, porque con Izipay se llama **después**: cuando el webhook aprueba
    el pago, la petición original terminó hace rato.

    Publicar ANTES del commit (`core/events.py`): el evento se bufferiza en la
    sesión y recién se despacha en `after_commit`."""
    cliente_id = None
    if pedido.cuenta_id is not None:
        cuenta = CuentaRepo(session).get(pedido.cuenta_id)
        cliente_id = cuenta.cliente_id if cuenta else None
    punto_venta = puntos_venta_web_de_sucursales(session, [pedido.sucursal_id]).get(
        pedido.sucursal_id
    )
    if punto_venta is None:
        raise ReglaNegocio("la sucursal del pedido ya no admite pedidos web")
    es_delivery = pedido.modalidad == "delivery"
    event_bus.publish(
        "storefront.pedido_web_confirmado",
        {
            "pedido_id": str(pedido.id),
            "idempotency_key": pedido.idempotency_key,
            "sucursal_id": str(pedido.sucursal_id),
            "punto_venta_id": str(punto_venta["punto_venta_id"]),
            "cliente_id": str(cliente_id) if cliente_id else None,
            "nombre_contacto": pedido.nombre_contacto,
            "telefono_contacto": pedido.telefono_contacto,
            "modalidad": pedido.modalidad,
            "items": [
                {
                    "producto_comercial_id": str(i.producto_comercial_id),
                    "cantidad": i.cantidad,
                    "valores_variante_ids": [v["id"] for v in (i.valores or [])],
                    "extras": [
                        {
                            "producto_comercial_id": e["producto_comercial_id"],
                            "cantidad": e["cantidad"],
                        }
                        for e in (i.extras or [])
                    ],
                }
                for i in PedidoItemRepo(session).listar(pedido.id)
            ],
            "direccion_entrega": pedido.direccion_entrega,
            "ubicacion": (
                {
                    "ubicacion_place_id": pedido.ubicacion_place_id,
                    "ubicacion_lat": str(pedido.ubicacion_lat) if pedido.ubicacion_lat else None,
                    "ubicacion_lng": str(pedido.ubicacion_lng) if pedido.ubicacion_lng else None,
                    "ubicacion_plus_code": pedido.ubicacion_plus_code,
                    "ubicacion_distrito": pedido.ubicacion_distrito,
                }
                if es_delivery
                else None
            ),
            "distancia_entrega_km": (
                str(pedido.distancia_km_estimada) if pedido.distancia_km_estimada else None
            ),
            "costo_entrega": (
                str(pedido.costo_delivery_estimado) if pedido.costo_delivery_estimado else None
            ),
            "medio_pago": pedido.medio_pago,
            # Solo con Izipay y ya aprobado: `sales` registra el pago con esta
            # referencia. En efectivo va `None` y la venta queda por cobrar.
            "pago_id_externo": (
                pedido.pago_id_externo if pedido.pago_estado == "aprobado" else None
            ),
            "numero_documento": pedido.numero_documento,
            "nombre_o_razon_social": pedido.nombre_o_razon_social,
        },
        session=session,
    )


def obtener_por_token(
    session: Session, pedido_id: uuid.UUID, token: str
) -> StorefrontPedido | None:
    """`GET /storefront/publico/pedidos/{id}?token=...` — un invitado sin
    cuenta consulta su propio pedido con el token que se le dio al
    confirmar, mismo patrón que `convocatoria.token_publico`."""
    pedido = PedidoRepo(session).get(pedido_id)
    if pedido is None or not secrets.compare_digest(pedido.token_acceso, token):
        return None
    return pedido
