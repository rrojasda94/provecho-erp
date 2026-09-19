"""Superficie pública del sitio de marca: sin JWT, protegida solo por rate
limit por IP (mismo patrón que `sales.api.publico_routers` y
`delivery.api.publico_routers`, ADR-105).

Regla de oro (RN-WEB-001): cada respuesta pasa por un `*PublicoOut` que
enumera sus campos — nunca se serializa un dict/ORM de otro módulo tal
cual. El checkout (`/pedidos*`, ADR-105) es la única excepción a "solo
lectura": admite invitados (RN-WEB-012, `get_cuenta_opcional` nunca exige
`Authorization`) y valida todo lo que llega antes de tocar la base.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.core.rate_limit import rate_limit
from src.modules.storefront.api import pedidos_schemas, schemas
from src.modules.storefront.api.deps import get_cuenta_opcional
from src.modules.storefront.application import pedidos, sitio
from src.modules.storefront.domain.carrito import LineaCarrito
from src.modules.storefront.infrastructure.models import StorefrontCuenta
from src.modules.storefront.infrastructure.repositories import PedidoItemRepo
from src.modules.users.api.deps import get_db

router = APIRouter(prefix="/storefront/publico", tags=["storefront"])

# Un sitio de marca se navega bastante más que la landing del QR: 120
# lecturas por hora y por IP cubren una visita completa (home, carta,
# varios productos, locales) con margen para varias visitas del mismo NAT
# —una familia mirando el menú desde la misma red— sin abrir la puerta a
# scrapear el catálogo entero a fuerza bruta.
_limite = rate_limit("storefront_publico", 120, 3600)
# El checkout es una escritura, no una lectura cacheada: tope más chico.
# 20/hora por IP cubre una familia pidiendo varias veces sin abrir la
# puerta a saturar la cocina a fuerza bruta.
_limite_pedidos = rate_limit("storefront_pedidos", 20, 3600)


def _cache(respuesta: Response) -> None:
    respuesta.headers["Cache-Control"] = "public, max-age=60"


@router.get("/contenido", response_model=schemas.ContenidoPublicoOut)
def ver_contenido(
    respuesta: Response,
    _=Depends(_limite),
    session: Session = Depends(get_db),
):
    _cache(respuesta)
    return sitio.contenido(session)


@router.get("/carta", response_model=schemas.CartaPublicaOut)
def ver_carta(
    respuesta: Response,
    _=Depends(_limite),
    session: Session = Depends(get_db),
):
    _cache(respuesta)
    return sitio.carta(session)


@router.get("/productos/{producto_id}", response_model=schemas.ProductoPublicoDetalleOut)
def ver_producto(
    producto_id: uuid.UUID,
    respuesta: Response,
    _=Depends(_limite),
    session: Session = Depends(get_db),
):
    _cache(respuesta)
    return sitio.producto(session, producto_id)


@router.get("/ingredientes/{articulo_id}", response_model=schemas.IngredientePublicoOut)
def ver_ingrediente(
    articulo_id: uuid.UUID,
    respuesta: Response,
    _=Depends(_limite),
    session: Session = Depends(get_db),
):
    _cache(respuesta)
    return sitio.ingrediente(session, articulo_id)


@router.get("/sucursales", response_model=list[schemas.SucursalPublicaOut])
def ver_sucursales(
    respuesta: Response,
    _=Depends(_limite),
    session: Session = Depends(get_db),
):
    _cache(respuesta)
    return sitio.sucursales(session)


@router.get("/promociones", response_model=list[schemas.PromocionPublicaWebOut])
def ver_promociones(
    respuesta: Response,
    _=Depends(_limite),
    session: Session = Depends(get_db),
):
    _cache(respuesta)
    return sitio.promociones(session)


@router.get("/convocatorias", response_model=list[schemas.ConvocatoriaPublicaWebOut])
def ver_convocatorias(
    respuesta: Response,
    _=Depends(_limite),
    session: Session = Depends(get_db),
):
    _cache(respuesta)
    return sitio.convocatorias(session)


def _pedido_out(session: Session, pedido, *, incluir_token: bool) -> dict:
    items = PedidoItemRepo(session).listar(pedido.id)
    return {
        "id": pedido.id,
        "estado": pedido.estado,
        "numero_orden": pedido.numero_orden,
        "fallo_motivo": pedido.fallo_motivo,
        "modalidad": pedido.modalidad,
        "sucursal_id": pedido.sucursal_id,
        "medio_pago": pedido.medio_pago,
        "total_estimado": pedido.total_estimado,
        "costo_delivery_estimado": pedido.costo_delivery_estimado,
        "eta_min": pedido.eta_min,
        "eta_max": pedido.eta_max,
        "token_acceso": pedido.token_acceso if incluir_token else None,
        "items": [
            {
                "nombre_congelado": i.nombre_congelado,
                "cantidad": i.cantidad,
                "precio_unitario_congelado": i.precio_unitario_congelado,
            }
            for i in items
        ],
    }


@router.post("/pedidos/cotizar", response_model=pedidos_schemas.CotizacionOut)
def cotizar_pedido(
    datos: pedidos_schemas.CotizarPedidoIn,
    _=Depends(_limite),
    session: Session = Depends(get_db),
):
    resultado = pedidos.cotizar(
        session,
        marca_id=sitio.marca_actual_id(),
        modalidad=datos.modalidad,
        sucursal_id=datos.sucursal_id,
        destino_lat=datos.ubicacion_lat,
        destino_lng=datos.ubicacion_lng,
        destino_distrito=datos.ubicacion_distrito,
        lineas=[
            LineaCarrito(producto_comercial_id=i.producto_comercial_id, cantidad=i.cantidad)
            for i in datos.items
        ],
    )
    return resultado


@router.post(
    "/pedidos", response_model=pedidos_schemas.PedidoOut, status_code=status.HTTP_201_CREATED
)
def confirmar_pedido(
    datos: pedidos_schemas.ConfirmarPedidoIn,
    _=Depends(_limite_pedidos),
    session: Session = Depends(get_db),
    cuenta: StorefrontCuenta | None = Depends(get_cuenta_opcional),
):
    pedido = pedidos.confirmar(
        session,
        marca_id=sitio.marca_actual_id(),
        cuenta_id=cuenta.id if cuenta else None,
        nombre_contacto=datos.nombre_contacto,
        telefono_contacto=datos.telefono_contacto,
        email_contacto=datos.email_contacto,
        modalidad=datos.modalidad,
        lineas=[
            LineaCarrito(producto_comercial_id=i.producto_comercial_id, cantidad=i.cantidad)
            for i in datos.items
        ],
        medio_pago=datos.medio_pago,
        numero_documento=datos.numero_documento,
        nombre_o_razon_social=datos.nombre_o_razon_social,
        idempotency_key=datos.idempotency_key,
        sucursal_id=datos.sucursal_id,
        direccion_entrega=datos.direccion_entrega,
        ubicacion_place_id=datos.ubicacion_place_id,
        ubicacion_lat=datos.ubicacion_lat,
        ubicacion_lng=datos.ubicacion_lng,
        ubicacion_plus_code=datos.ubicacion_plus_code,
        ubicacion_distrito=datos.ubicacion_distrito,
    )
    return _pedido_out(session, pedido, incluir_token=True)


@router.get("/pedidos/{pedido_id}", response_model=pedidos_schemas.PedidoOut)
def ver_pedido(
    pedido_id: uuid.UUID,
    token: str,
    _=Depends(_limite),
    session: Session = Depends(get_db),
):
    pedido = pedidos.obtener_por_token(session, pedido_id, token)
    if pedido is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no encontrado")
    return _pedido_out(session, pedido, incluir_token=False)
