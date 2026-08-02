"""Router del KDS: configuración de pantallas, cola, bump, avance y comanda.

Permisos: `kds.configurar` (crear/editar pantallas — admin/supervisor),
`kds.operar` (cocina: cola, bump, comanda). Consultar avance solo exige
operar o leer ventas.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.sales.api import kds_schemas as schemas
from src.modules.sales.application import kds
from src.modules.sales.application.scope import (
    exigir_pantalla,
    exigir_venta,
    exigir_venta_item,
)
from src.modules.users.api.deps import get_db, get_tenant, require_permission
from src.modules.users.infrastructure.models import Usuario

router = APIRouter(prefix="/kds", tags=["kds"])

CONFIGURAR = "kds.configurar"
OPERAR = "kds.operar"


# --- Configuración ------------------------------------------------------------
@router.post("/pantallas", response_model=schemas.PantallaOut, status_code=201)
def crear_pantalla(
    body: schemas.PantallaCreate,
    _: Usuario = Depends(require_permission(CONFIGURAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    tenant.exigir_sucursal(body.sucursal_id)
    pantalla = kds.crear_pantalla(session, **body.model_dump())
    session.commit()
    return pantalla


@router.get("/pantallas", response_model=list[schemas.PantallaOut])
def listar_pantallas(
    sucursal_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(OPERAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    if sucursal_id is not None:
        tenant.exigir_sucursal(sucursal_id)
    pantallas = kds.listar_pantallas(session, sucursal_id)
    if tenant.superusuario:
        return pantallas
    return [p for p in pantallas if p.sucursal_id in tenant.sucursal_ids]


@router.patch("/pantallas/{pantalla_id}", response_model=schemas.PantallaOut)
def editar_pantalla(
    pantalla_id: uuid.UUID,
    body: schemas.PantallaUpdate,
    _: Usuario = Depends(require_permission(CONFIGURAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_pantalla(session, pantalla_id, tenant)
    pantalla = kds.editar_pantalla(session, pantalla_id, **body.model_dump())
    session.commit()
    return pantalla


# --- Operación ------------------------------------------------------------------
@router.get("/pantallas/{pantalla_id}/cola", response_model=list[schemas.PedidoColaOut])
def cola(
    pantalla_id: uuid.UUID,
    _: Usuario = Depends(require_permission(OPERAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_pantalla(session, pantalla_id, tenant)
    return kds.cola_pantalla(session, pantalla_id)


@router.post("/items/{venta_item_id}/avanzar", response_model=schemas.ItemColaOut)
def avanzar(
    venta_item_id: uuid.UUID,
    body: schemas.AvanzarIn,
    _: Usuario = Depends(require_permission(OPERAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_venta_item(session, venta_item_id, tenant)
    item = kds.avanzar_item(session, venta_item_id, body.estado)
    session.commit()
    return schemas.ItemColaOut(
        venta_item_id=str(item.id), producto="", cantidad=str(item.cantidad),
        estado=item.estado_preparacion,
    )


@router.get("/ventas/{venta_id}/avance", response_model=schemas.AvanceOut)
def avance(
    venta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(OPERAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_venta(session, venta_id, tenant)
    return kds.avance_venta(session, venta_id)


@router.post("/ventas/{venta_id}/comanda", response_model=schemas.ComandaOut)
def imprimir_comanda(
    venta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(OPERAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_venta(session, venta_id, tenant)
    resultado = kds.comanda(session, venta_id)
    session.commit()
    return resultado
