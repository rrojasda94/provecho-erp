"""Routers FastAPI del módulo purchases: proveedores y ciclo de OC."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.tenant import Tenant
from src.modules.purchases.api import schemas
from src.modules.purchases.application import compra_directa, comprobantes, ordenes, proveedores
from src.modules.purchases.application.scope import (
    exigir_almacen,
    exigir_orden_compra,
    exigir_proveedor,
)
from src.modules.users.api.deps import get_db, get_tenant, require_permission
from src.modules.users.application.queries_publicas import tiene_permiso
from src.modules.users.infrastructure.models import Usuario
from src.shared.paginacion import Pagina, Paginacion, paginacion, paginar

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
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos["empresa_id"])
    proveedor = proveedores.crear_proveedor(session, **campos)
    session.commit()
    return proveedor


@router.get("/proveedores", response_model=Pagina[schemas.ProveedorOut])
def listar_proveedores(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    return paginar(
        session,
        proveedores.q_proveedores(session, tenant.filtro_empresa(empresa_id)),
        p,
    )


@router.patch("/proveedores/{proveedor_id}", response_model=schemas.ProveedorOut)
def editar_proveedor(
    proveedor_id: uuid.UUID,
    body: schemas.ProveedorUpdate,
    _: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_proveedor(session, proveedor_id, tenant)
    proveedor = proveedores.editar_proveedor(session, proveedor_id, **body.model_dump())
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
    session.commit()
    return orden


@router.get("/ordenes-compra", response_model=Pagina[schemas.OrdenCompraOut])
def listar_ordenes_compra(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    return paginar(
        session,
        ordenes.q_ordenes_compra(session, tenant.filtro_empresa(empresa_id)),
        p,
    )


def _con_items(session: Session, orden) -> schemas.OrdenCompraOut:
    salida = schemas.OrdenCompraOut.model_validate(orden)
    salida.items = [
        schemas.OrdenCompraItemOut.model_validate(it)
        for it in ordenes.items_de_orden_compra(session, orden.id)
    ]
    return salida


@router.get("/ordenes-compra/{orden_compra_id}", response_model=schemas.OrdenCompraOut)
def ver_orden_compra(
    orden_compra_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    orden = exigir_orden_compra(session, orden_compra_id, tenant)
    return _con_items(session, orden)


@router.patch("/ordenes-compra/{orden_compra_id}", response_model=schemas.OrdenCompraOut)
def editar_orden_compra(
    orden_compra_id: uuid.UUID,
    body: schemas.OrdenCompraItemsUpdate,
    actor: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_orden_compra(session, orden_compra_id, tenant)
    orden = ordenes.editar_orden_compra(
        session,
        orden_compra_id,
        items=[it.model_dump() for it in body.items],
        actor_id=actor.id,
    )
    session.commit()
    return _con_items(session, orden)


@router.post("/ordenes-compra/{orden_compra_id}/emitir", response_model=schemas.OrdenCompraOut)
def emitir_orden_compra(
    orden_compra_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_orden_compra(session, orden_compra_id, tenant)
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
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_orden_compra(session, orden_compra_id, tenant)
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
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_orden_compra(session, orden_compra_id, tenant)
    orden = ordenes.anular_orden_compra(session, orden_compra_id, actor.id)
    session.commit()
    return orden


@router.post("/compras-directas", response_model=schemas.ComprobanteOut, status_code=201)
def registrar_compra_directa(
    body: schemas.CompraDirectaCreate,
    actor: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_proveedor(session, body.proveedor_id, tenant)
    exigir_almacen(session, body.almacen_destino_id, tenant)
    comprobante = compra_directa.registrar_compra_directa(
        session,
        proveedor_id=body.proveedor_id,
        almacen_destino_id=body.almacen_destino_id,
        creado_por=actor.id,
        idempotency_key=body.idempotency_key,
        items=[it.model_dump() for it in body.items],
        comprobante=body.comprobante.model_dump(),
    )
    session.commit()
    return comprobante


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
    exigir_orden_compra(session, orden_compra_id, tenant)
    comprobante = comprobantes.dar_conformidad_comprobante(
        session, orden_compra_id, **body.model_dump()
    )
    session.commit()
    return comprobante
