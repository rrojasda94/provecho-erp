"""Superficie pública del sitio de marca: sin JWT, protegida solo por rate
limit por IP (mismo patrón que `sales.api.publico_routers` y
`delivery.api.publico_routers`, ADR-103).

Regla de oro (RN-WEB-001): cada respuesta pasa por un `*PublicoOut` que
enumera sus campos — nunca se serializa un dict/ORM de otro módulo tal
cual. Solo lectura: no hay ningún `POST`/`PATCH`/`DELETE` en este router.
"""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.core.rate_limit import rate_limit
from src.modules.storefront.api import schemas
from src.modules.storefront.application import sitio
from src.modules.users.api.deps import get_db

router = APIRouter(prefix="/storefront/publico", tags=["storefront"])

# Un sitio de marca se navega bastante más que la landing del QR: 120
# lecturas por hora y por IP cubren una visita completa (home, carta,
# varios productos, locales) con margen para varias visitas del mismo NAT
# —una familia mirando el menú desde la misma red— sin abrir la puerta a
# scrapear el catálogo entero a fuerza bruta.
_limite = rate_limit("storefront_publico", 120, 3600)


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
