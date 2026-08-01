"""Routers FastAPI del módulo purchases: proveedores y ciclo de OC."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.modules.purchases.api import schemas
from src.modules.purchases.application import comprobantes, ordenes, proveedores
from src.modules.users.api.deps import get_db, require_permission
from src.modules.users.application.queries_publicas import tiene_permiso
from src.modules.users.infrastructure.models import Usuario

router = APIRouter(prefix="/purchases", tags=["purchases"])

CREAR = "purchases.crear"
LEER = "purchases.leer"
RECEPCIONAR = "purchases.recepcionar"
ANULAR = "purchases.anular"
APROBAR = "purchases.aprobar"
DAR_CONFORMIDAD = "purchases.dar_conformidad"


# --- Proveedores -------------------------------------------------------------
@router.post("/proveedores", response_model=schemas.ProveedorOut, status_code=201)
def crear_proveedor(
    body: schemas.ProveedorCreate,
    _: Usuario = Depends(require_permission(CREAR)),
    session: Session = Depends(get_db),
):
    proveedor = proveedores.crear_proveedor(session, **body.model_dump())
    session.commit()
    return proveedor


@router.get("/proveedores", response_model=list[schemas.ProveedorOut])
def listar_proveedores(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return proveedores.listar_proveedores(session, empresa_id)


@router.patch("/proveedores/{proveedor_id}", response_model=schemas.ProveedorOut)
def editar_proveedor(
    proveedor_id: uuid.UUID,
    body: schemas.ProveedorUpdate,
    _: Usuario = Depends(require_permission(CREAR)),
    session: Session = Depends(get_db),
):
    proveedor = proveedores.editar_proveedor(session, proveedor_id, **body.model_dump())
    session.commit()
    return proveedor


# --- Orden de compra ----------------------------------------------------------
@router.post("/ordenes-compra", response_model=schemas.OrdenCompraOut, status_code=201)
def crear_orden_compra(
    body: schemas.OrdenCompraCreate,
    actor: Usuario = Depends(require_permission(CREAR)),
    session: Session = Depends(get_db),
):
    orden = ordenes.crear_orden_compra(
        session,
        proveedor_id=body.proveedor_id,
        almacen_destino_id=body.almacen_destino_id,
        creado_por=actor.id,
        idempotency_key=body.idempotency_key,
        items=[it.model_dump() for it in body.items],
        tipo=body.tipo,
    )
    session.commit()
    return orden


@router.get("/ordenes-compra/{orden_compra_id}", response_model=schemas.OrdenCompraOut)
def ver_orden_compra(
    orden_compra_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    from src.modules.purchases.infrastructure.repositories import OrdenCompraRepo

    orden = OrdenCompraRepo(session).get(orden_compra_id)
    if orden is None:
        raise HTTPException(404, "orden de compra no encontrada")
    return orden


@router.post("/ordenes-compra/{orden_compra_id}/emitir", response_model=schemas.OrdenCompraOut)
def emitir_orden_compra(
    orden_compra_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(CREAR)),
    session: Session = Depends(get_db),
):
    puede_aprobar = tiene_permiso(session, actor.id, APROBAR)
    orden = ordenes.emitir_orden_compra(
        session,
        orden_compra_id,
        actor_id=actor.id,
        puede_aprobar_monto=puede_aprobar,
        umbral_aprobacion=settings.purchases_umbral_aprobacion_oc,
    )
    session.commit()
    return orden


@router.post(
    "/ordenes-compra/{orden_compra_id}/recepciones",
    response_model=schemas.RecepcionOut,
    status_code=201,
)


def recibir_orden_compra(
    orden_compra_id: uuid.UUID,
    body: schemas.RecepcionCreate,
    actor: Usuario = Depends(require_permission(RECEPCIONAR)),
    session: Session = Depends(get_db),
):
    recepcion = ordenes.recibir_orden_compra(
        session,
        orden_compra_id,
        recibido_por=actor.id,
        idempotency_key=body.idempotency_key,
        items=[it.model_dump() for it in body.items],
    )
    session.commit()
    return recepcion


@router.post("/ordenes-compra/{orden_compra_id}/anular", response_model=schemas.OrdenCompraOut)
def anular_orden_compra(
    orden_compra_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(ANULAR)),
    session: Session = Depends(get_db),
):
    orden = ordenes.anular_orden_compra(session, orden_compra_id, actor.id)
    session.commit()
    return orden


@router.post(
    "/ordenes-compra/{orden_compra_id}/conformidad-comprobante",
    response_model=schemas.ComprobanteOut,
    status_code=201,
)


def dar_conformidad_comprobante(
    orden_compra_id: uuid.UUID,
    body: schemas.ConformidadComprobanteCreate,
    _: Usuario = Depends(require_permission(DAR_CONFORMIDAD)),
    session: Session = Depends(get_db),
):
    comprobante = comprobantes.dar_conformidad_comprobante(
        session, orden_compra_id, **body.model_dump()
    )
    session.commit()
    return comprobante
