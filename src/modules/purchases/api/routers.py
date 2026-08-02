"""Routers FastAPI del módulo purchases: proveedores y ciclo de OC."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.tenant import Tenant
from src.modules.purchases.api import schemas
from src.modules.purchases.application import comprobantes, ordenes, proveedores
from src.modules.purchases.application.errors import (
    Conflicto,
    NoEncontrado,
    PurchasesError,
    ReglaNegocio,
)
from src.modules.purchases.application.scope import (
    exigir_almacen,
    exigir_orden_compra,
    exigir_proveedor,
)
from src.modules.users.api.deps import get_db, get_tenant, require_permission
from src.modules.users.domain.rules import permite
from src.modules.users.infrastructure.models import Usuario
from src.modules.users.infrastructure.repositories import UsuarioRepo

router = APIRouter(prefix="/purchases", tags=["purchases"])

CREAR = "purchases.crear"
LEER = "purchases.leer"
RECEPCIONAR = "purchases.recepcionar"
ANULAR = "purchases.anular"
APROBAR = "purchases.aprobar"
DAR_CONFORMIDAD = "purchases.dar_conformidad"

_HTTP_STATUS: dict[type[PurchasesError], int] = {
    NoEncontrado: status.HTTP_404_NOT_FOUND,
    Conflicto: status.HTTP_409_CONFLICT,
    ReglaNegocio: status.HTTP_409_CONFLICT,
}


def _http(err: PurchasesError) -> HTTPException:
    return HTTPException(_HTTP_STATUS.get(type(err), 400), str(err))


# --- Proveedores -------------------------------------------------------------
@router.post("/proveedores", response_model=schemas.ProveedorOut, status_code=201)
def crear_proveedor(
    body: schemas.ProveedorCreate,
    _: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos["empresa_id"])
    try:
        proveedor = proveedores.crear_proveedor(session, **campos)
    except (NoEncontrado, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return proveedor


@router.get("/proveedores", response_model=list[schemas.ProveedorOut])
def listar_proveedores(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return proveedores.listar_proveedores(session, tenant.filtro_empresa(empresa_id))


@router.patch("/proveedores/{proveedor_id}", response_model=schemas.ProveedorOut)
def editar_proveedor(
    proveedor_id: uuid.UUID,
    body: schemas.ProveedorUpdate,
    _: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_proveedor(session, proveedor_id, tenant)
        proveedor = proveedores.editar_proveedor(session, proveedor_id, **body.model_dump())
    except NoEncontrado as e:
        raise _http(e) from e
    session.commit()
    return proveedor


# --- Orden de compra ----------------------------------------------------------
@router.post("/ordenes-compra", response_model=schemas.OrdenCompraOut, status_code=201)
def crear_orden_compra(
    body: schemas.OrdenCompraCreate,
    actor: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_proveedor(session, body.proveedor_id, tenant)
        exigir_almacen(session, body.almacen_destino_id, tenant)
        orden = ordenes.crear_orden_compra(
            session,
            proveedor_id=body.proveedor_id,
            almacen_destino_id=body.almacen_destino_id,
            creado_por=actor.id,
            idempotency_key=body.idempotency_key,
            items=[it.model_dump() for it in body.items],
            tipo=body.tipo,
        )
    except (NoEncontrado, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return orden


@router.get("/ordenes-compra/{orden_compra_id}", response_model=schemas.OrdenCompraOut)
def ver_orden_compra(
    orden_compra_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        return exigir_orden_compra(session, orden_compra_id, tenant)
    except NoEncontrado as e:
        raise _http(e) from e


@router.post("/ordenes-compra/{orden_compra_id}/emitir", response_model=schemas.OrdenCompraOut)
def emitir_orden_compra(
    orden_compra_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    puede_aprobar = permite(UsuarioRepo(session).permiso_codigos(actor.id), APROBAR)
    try:
        exigir_orden_compra(session, orden_compra_id, tenant)
        orden = ordenes.emitir_orden_compra(
            session,
            orden_compra_id,
            actor_id=actor.id,
            puede_aprobar_monto=puede_aprobar,
            umbral_aprobacion=settings.purchases_umbral_aprobacion_oc,
        )
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
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
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_orden_compra(session, orden_compra_id, tenant)
        recepcion = ordenes.recibir_orden_compra(
            session,
            orden_compra_id,
            recibido_por=actor.id,
            idempotency_key=body.idempotency_key,
            items=[it.model_dump() for it in body.items],
        )
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return recepcion


@router.post("/ordenes-compra/{orden_compra_id}/anular", response_model=schemas.OrdenCompraOut)
def anular_orden_compra(
    orden_compra_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(ANULAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_orden_compra(session, orden_compra_id, tenant)
        orden = ordenes.anular_orden_compra(session, orden_compra_id, actor.id)
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
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
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_orden_compra(session, orden_compra_id, tenant)
        comprobante = comprobantes.dar_conformidad_comprobante(
            session, orden_compra_id, **body.model_dump()
        )
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return comprobante
