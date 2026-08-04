"""Routers FastAPI del módulo production: orden de producción."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.tenant import Tenant
from src.modules.production.api import schemas
from src.modules.production.application import ordenes
from src.modules.production.application.scope import exigir_almacen, exigir_orden
from src.modules.users.api.deps import get_db, get_tenant, require_permission
from src.modules.users.infrastructure.models import Usuario
from src.shared.paginacion import Pagina, Paginacion, paginacion, paginar

router = APIRouter(prefix="/production", tags=["production"])

CREAR = "production.crear"
LEER = "production.leer"
COMPLETAR = "production.completar"


@router.post("/ordenes", response_model=schemas.OrdenProduccionOut, status_code=201)
def crear_orden(
    body: schemas.OrdenProduccionCreate,
    actor: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_almacen(session, body.almacen_id, tenant)
    orden = ordenes.crear_orden_produccion(
        session,
        articulo_id=body.articulo_id,
        almacen_id=body.almacen_id,
        cantidad_planeada=body.cantidad_planeada,
        creado_por=actor.id,
        idempotency_key=body.idempotency_key,
    )
    session.commit()
    return orden


@router.get("/ordenes", response_model=Pagina[schemas.OrdenProduccionOut])
def listar_ordenes(
    almacen_id: uuid.UUID | None = None,
    estado: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """Las órdenes del alcance del usuario, la más reciente primero.

    No existía: solo se podía ver una orden si ya se sabía su id, lo que
    dejaba a la cocina sin forma de mirar su propia jornada.
    """
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return paginar(
        session,
        ordenes.q_ordenes(
            session,
            empresa_id=tenant.filtro_empresa(),
            almacen_id=almacen_id,
            estado=estado,
        ),
        p,
    )


@router.get("/ordenes/{orden_id}", response_model=schemas.OrdenProduccionOut)
def ver_orden(
    orden_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_orden(session, orden_id, tenant)


@router.post("/ordenes/{orden_id}/consumo", response_model=schemas.OrdenProduccionOut)
def registrar_consumo(
    orden_id: uuid.UUID,
    body: schemas.ConsumoCreate,
    _: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_orden(session, orden_id, tenant)
    orden = ordenes.registrar_consumo(
        session, orden_id, items=[it.model_dump() for it in body.items]
    )
    session.commit()
    return orden


@router.post("/ordenes/{orden_id}/completar", response_model=schemas.OrdenProduccionOut)
def completar_orden(
    orden_id: uuid.UUID,
    body: schemas.CompletarOrdenIn,
    _: Usuario = Depends(require_permission(COMPLETAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_orden(session, orden_id, tenant)
    orden = ordenes.completar_orden_produccion(
        session,
        orden_id,
        resultado=body.resultado,
        costo_hora_mano_obra=settings.production_costo_hora_mano_obra,
        cantidad_producida=body.cantidad_producida,
        horas_hombre=body.horas_hombre,
        merma_cantidad=body.merma_cantidad,
        merma_motivo=body.merma_motivo,
        evidencia_destruccion_url=body.evidencia_destruccion_url,
    )
    session.commit()
    return orden
