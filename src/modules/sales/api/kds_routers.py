"""Router del KDS: configuración de pantallas, cola, bump, avance y comanda.

Permisos: `kds.configurar` (crear, editar y borrar pantallas — solo
administración desde 2026-08-24, ADR-065), `kds.operar` (cocina: cola,
bump, comanda). Listar pantallas acepta cualquiera de los dos: quien las
administra tiene que poder ver lo que administra sin operar la cocina.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.sales.api import kds_schemas as schemas
from src.modules.sales.application import kds, kds_semaforo
from src.modules.sales.application.scope import (
    exigir_pantalla,
    exigir_venta,
    exigir_venta_item,
)
from src.modules.users.api.deps import (
    check_permission,
    get_current_user,
    get_db,
    get_tenant,
    require_permission,
)
from src.modules.users.infrastructure.models import Sucursal, Usuario

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
    usuario: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    check_permission(session, usuario, OPERAR, CONFIGURAR)
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
    # La sucursal destino también tiene que ser suya: sin esto, quien puede
    # editar sus pantallas podría mandar una a la cocina de otra empresa.
    if body.sucursal_id is not None:
        tenant.exigir_sucursal(body.sucursal_id)
    pantalla = kds.editar_pantalla(session, pantalla_id, **body.model_dump())
    session.commit()
    return pantalla


@router.delete("/pantallas/{pantalla_id}", status_code=204)
def eliminar_pantalla(
    pantalla_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CONFIGURAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_pantalla(session, pantalla_id, tenant)
    kds.eliminar_pantalla(session, pantalla_id)
    session.commit()


@router.get("/configuracion", response_model=schemas.SemaforoOut)
def configuracion(
    sucursal_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(OPERAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Umbrales y colores del semáforo, ya resueltos.

    Permiso de cocina y no de Gerencia: la pantalla necesita **leerlos** para
    pintar, aprobarlos es otra cosa (`POST /parametros`). `sucursal_id` es
    para superusuarios sin empresa en el token — el parámetro es por empresa,
    así que se usa solo para resolver de cuál.
    """
    empresa_id = tenant.empresa_id
    if empresa_id is None and sucursal_id is not None:
        empresa_id = _empresa_de_sucursal(session, sucursal_id, tenant)
    return kds_semaforo.semaforo_de(session, empresa_id)


def _empresa_de_sucursal(
    session: Session, sucursal_id: uuid.UUID, tenant: Tenant
) -> uuid.UUID | None:
    tenant.exigir_sucursal(sucursal_id)
    sucursal = session.get(Sucursal, sucursal_id)
    return sucursal.empresa_id if sucursal is not None else None


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
        estado=item.estado_preparacion, etapa_kds=item.etapa_kds,
    )


@router.post("/items/{venta_item_id}/retroceder", response_model=schemas.ItemColaOut)
def retroceder(
    venta_item_id: uuid.UUID,
    _: Usuario = Depends(require_permission(OPERAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Deshace un paso del avance de la línea (RN-CUP-002, enmendada
    2026-08-26). Sin cuerpo: no se salta a un estado arbitrario, se deshace
    lo último que se hizo. `kds.operar` y no un permiso nuevo — quien se
    equivoca tachando es quien tiene que poder corregirlo, en el momento."""
    exigir_venta_item(session, venta_item_id, tenant)
    item = kds.retroceder_item(session, venta_item_id)
    session.commit()
    return schemas.ItemColaOut(
        venta_item_id=str(item.id), producto="", cantidad=str(item.cantidad),
        estado=item.estado_preparacion, etapa_kds=item.etapa_kds,
    )


@router.get(
    "/pantallas/{pantalla_id}/historial",
    response_model=list[schemas.PedidoHistorialOut],
)
def historial(
    pantalla_id: uuid.UUID,
    # Días de negocio, no horas: `dias=1` es hoy, `dias=2` hoy y ayer.
    dias: int = Query(default=kds.DIAS_HISTORIAL, ge=1, le=7),
    _: Usuario = Depends(require_permission(OPERAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Lo que esta pantalla ya despachó. La cola descarta los pedidos
    entregados y hasta ahora eso era todo: uno entregado por error
    desaparecía sin dejar dónde buscarlo."""
    exigir_pantalla(session, pantalla_id, tenant)
    return kds.historial_pantalla(session, pantalla_id, dias)


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
