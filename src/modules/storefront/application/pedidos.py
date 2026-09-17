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
)
from src.modules.storefront.application.errors import NoEncontrado, ReglaNegocio
from src.modules.storefront.domain import asignacion, carrito
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


def _resolver_sucursal(
    session: Session,
    *,
    marca_id: uuid.UUID,
    modalidad: str,
    sucursal_id: uuid.UUID | None,
    destino_lat: Decimal | None,
    destino_lng: Decimal | None,
    destino_distrito: str | None,
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

    if modalidad == "takeout":
        if sucursal_id is None:
            raise ReglaNegocio("elige un local para recojo")
        elegida = next((s for s in elegibles if s.id == sucursal_id), None)
        if elegida is None:
            raise NoEncontrado("esa sucursal no admite recojo por el sitio")
        carga = cargas.get(elegida.id, 0)
        eta_min, eta_max = asignacion.estimar_eta(
            carga,
            base_minutos=settings.storefront_eta_base_minutos,
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
    eta_min, eta_max = asignacion.estimar_eta(
        elegida.carga,
        base_minutos=settings.storefront_eta_base_minutos,
        minutos_por_pedido=settings.storefront_eta_minutos_por_pedido,
    )
    cotizacion = cotizaciones[elegida.sucursal_id]
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
) -> dict:
    """Vista previa antes de confirmar: a qué sucursal iría el pedido, con
    qué ETA y (delivery) a qué costo — para mostrarlo en el checkout antes
    de que el cliente decida."""
    r = _resolver_sucursal(
        session,
        marca_id=marca_id,
        modalidad=modalidad,
        sucursal_id=sucursal_id,
        destino_lat=destino_lat,
        destino_lng=destino_lng,
        destino_distrito=destino_distrito,
    )
    return {
        "sucursal_id": r.sucursal_id,
        "eta_min": r.eta_min,
        "eta_max": r.eta_max,
        "costo_delivery": r.costo_delivery,
        "distancia_km": r.distancia_km,
    }


def _precios_de_carta(
    session: Session, *, marca_id: uuid.UUID, sucursal_id: uuid.UUID, modalidad: str
) -> dict[uuid.UUID, tuple[Decimal, bool, str]]:
    """`{producto_comercial_id: (precio_unitario, disponible, nombre)}` de
    todo lo que aparece en la carta pública de esa sucursal — el mismo
    precio que ve el cliente al armar el carrito. Es una foto para mostrar,
    no la fuente de verdad: `crear_venta` vuelve a fijar el precio server-
    side al confirmar (RN-PRC-003)."""
    items = carta_publica(
        session,
        marca_id=marca_id,
        sucursal_id=sucursal_id,
        canal=settings.storefront_canal,
        modalidad=modalidad,
    )
    precios: dict[uuid.UUID, tuple[Decimal, bool, str]] = {}
    for item in items:
        precios[item["producto_comercial_id"]] = (
            item["precio_unitario"],
            not item["stock_bajo"],
            item["nombre"],
        )
        for variante in item.get("variantes", []):
            precios[variante["producto_comercial_id"]] = (
                variante["precio_unitario"],
                not variante["stock_bajo"],
                variante["nombre"],
            )
    return precios


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
    if medio_pago not in ("efectivo", "izipay"):
        raise ReglaNegocio(f"medio de pago inválido: {medio_pago}")
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
    )

    precios = _precios_de_carta(
        session, marca_id=marca_id, sucursal_id=r.sucursal_id, modalidad=modalidad
    )
    total = Decimal("0")
    items_payload = []
    items_congelados = []
    for linea in lineas:
        datos = precios.get(linea.producto_comercial_id)
        if datos is None:
            raise NoEncontrado("un producto del carrito ya no está en la carta")
        precio, disponible, nombre = datos
        if not disponible:
            raise ReglaNegocio(f"'{nombre}' no está disponible ahora mismo")
        total += precio * linea.cantidad
        items_payload.append(
            {
                "producto_comercial_id": str(linea.producto_comercial_id),
                "cantidad": linea.cantidad,
            }
        )
        items_congelados.append((linea.producto_comercial_id, nombre, linea.cantidad, precio))
    if r.costo_delivery:
        total += r.costo_delivery

    cliente_id = None
    if cuenta_id is not None:
        cuenta = CuentaRepo(session).get(cuenta_id)
        cliente_id = cuenta.cliente_id if cuenta else None

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
    item_repo = PedidoItemRepo(session)
    for producto_id, nombre, cantidad, precio in items_congelados:
        item_repo.add(
            StorefrontPedidoItem(
                pedido_id=pedido.id,
                producto_comercial_id=producto_id,
                nombre_congelado=nombre,
                cantidad=cantidad,
                precio_unitario_congelado=precio,
            )
        )

    # Publicar ANTES del commit (`core/events.py`): se bufferiza en la
    # sesión y recién se despacha en `after_commit`.
    event_bus.publish(
        "storefront.pedido_web_confirmado",
        {
            "pedido_id": str(pedido.id),
            "idempotency_key": idempotency_key,
            "sucursal_id": str(r.sucursal_id),
            "punto_venta_id": str(r.punto_venta_id),
            "cliente_id": str(cliente_id) if cliente_id else None,
            "nombre_contacto": nombre_contacto,
            "modalidad": modalidad,
            "items": items_payload,
            "direccion_entrega": direccion_entrega,
            "ubicacion": (
                {
                    "ubicacion_place_id": ubicacion_place_id,
                    "ubicacion_lat": str(ubicacion_lat) if ubicacion_lat else None,
                    "ubicacion_lng": str(ubicacion_lng) if ubicacion_lng else None,
                    "ubicacion_plus_code": ubicacion_plus_code,
                    "ubicacion_distrito": ubicacion_distrito,
                }
                if modalidad == "delivery"
                else None
            ),
            "distancia_entrega_km": str(r.distancia_km) if r.distancia_km else None,
            "costo_entrega": str(r.costo_delivery) if r.costo_delivery else None,
            "medio_pago": medio_pago,
            "numero_documento": numero_documento,
            "nombre_o_razon_social": nombre_o_razon_social,
        },
        session=session,
    )
    session.commit()
    session.refresh(pedido)
    return pedido


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
