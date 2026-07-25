"""Router del KDS: configuración de pantallas, cola, bump, avance y comanda.

Permisos: `kds.configurar` (crear/editar pantallas — admin/supervisor),
`kds.operar` (cocina: cola, bump, comanda). Consultar avance solo exige
operar o leer ventas.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.modules.sales.api import kds_schemas as schemas
from src.modules.sales.application import kds
from src.modules.sales.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
    SalesError,
)
from src.modules.users.api.deps import get_db, require_permission
from src.modules.users.infrastructure.models import Usuario

router = APIRouter(prefix="/kds", tags=["kds"])

CONFIGURAR = "kds.configurar"
OPERAR = "kds.operar"

_HTTP_STATUS: dict[type[SalesError], int] = {
    NoEncontrado: status.HTTP_404_NOT_FOUND,
    Conflicto: status.HTTP_409_CONFLICT,
    ReglaNegocio: status.HTTP_409_CONFLICT,
}


def _http(err: SalesError) -> HTTPException:
    return HTTPException(_HTTP_STATUS.get(type(err), 400), str(err))


# --- Configuración ------------------------------------------------------------
@router.post("/pantallas", response_model=schemas.PantallaOut, status_code=201)
def crear_pantalla(
    body: schemas.PantallaCreate,
    _: Usuario = Depends(require_permission(CONFIGURAR)),
    session: Session = Depends(get_db),
):
    try:
        pantalla = kds.crear_pantalla(session, **body.model_dump())
    except (Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return pantalla


@router.get("/pantallas", response_model=list[schemas.PantallaOut])
def listar_pantallas(
    sucursal_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(OPERAR)),
    session: Session = Depends(get_db),
):
    return kds.listar_pantallas(session, sucursal_id)


@router.patch("/pantallas/{pantalla_id}", response_model=schemas.PantallaOut)
def editar_pantalla(
    pantalla_id: uuid.UUID,
    body: schemas.PantallaUpdate,
    _: Usuario = Depends(require_permission(CONFIGURAR)),
    session: Session = Depends(get_db),
):
    try:
        pantalla = kds.editar_pantalla(session, pantalla_id, **body.model_dump())
    except (NoEncontrado, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return pantalla


# --- Operación ------------------------------------------------------------------
@router.get("/pantallas/{pantalla_id}/cola", response_model=list[schemas.PedidoColaOut])
def cola(
    pantalla_id: uuid.UUID,
    _: Usuario = Depends(require_permission(OPERAR)),
    session: Session = Depends(get_db),
):
    try:
        return kds.cola_pantalla(session, pantalla_id)
    except NoEncontrado as e:
        raise _http(e) from e


@router.post("/items/{venta_item_id}/avanzar", response_model=schemas.ItemColaOut)
def avanzar(
    venta_item_id: uuid.UUID,
    body: schemas.AvanzarIn,
    _: Usuario = Depends(require_permission(OPERAR)),
    session: Session = Depends(get_db),
):
    try:
        item = kds.avanzar_item(session, venta_item_id, body.estado)
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return schemas.ItemColaOut(
        venta_item_id=str(item.id), producto="", cantidad=str(item.cantidad),
        estado=item.estado_preparacion,
    )


@router.get("/ventas/{venta_id}/avance", response_model=schemas.AvanceOut)
def avance(
    venta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(OPERAR)),
    session: Session = Depends(get_db),
):
    try:
        return kds.avance_venta(session, venta_id)
    except NoEncontrado as e:
        raise _http(e) from e


@router.post("/ventas/{venta_id}/comanda", response_model=schemas.ComandaOut)
def imprimir_comanda(
    venta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(OPERAR)),
    session: Session = Depends(get_db),
):
    try:
        resultado = kds.comanda(session, venta_id)
    except NoEncontrado as e:
        raise _http(e) from e
    session.commit()
    return resultado
