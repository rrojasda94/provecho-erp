"""Routers FastAPI del módulo production: orden de producción."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.production.api import schemas
from src.modules.production.application import (
    evidencia,
    inocuidad,
    ordenes,
    planes,
    reportes_jornada,
    tarifas,
)
from src.modules.production.application.scope import (
    exigir_almacen,
    exigir_checklist,
    exigir_orden,
    exigir_plan,
    exigir_reporte_jornada,
)
from src.modules.rrhh.application import queries_publicas as rrhh_queries
from src.modules.users.api.deps import client_ip, get_db, get_tenant, require_permission
from src.modules.users.infrastructure.models import Almacen, Usuario
from src.shared.paginacion import Pagina, Paginacion, paginacion, paginar

router = APIRouter(prefix="/production", tags=["production"])

CREAR = "production.crear"
LEER = "production.leer"
COMPLETAR = "production.completar"
PLANIFICAR = "production.planificar"
VERIFICAR_INOCUIDAD = "production.verificar_inocuidad"
VISAR_REPORTE_JORNADA = "production.visar_reporte_jornada"


@router.post("/ordenes", response_model=schemas.OrdenProduccionOut, status_code=201)
def crear_orden(
    body: schemas.OrdenProduccionCreate,
    actor: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
    ip: str | None = Depends(client_ip),
):
    exigir_almacen(session, body.almacen_id, tenant)
    orden = ordenes.crear_orden_produccion(
        session,
        articulo_id=body.articulo_id,
        almacen_id=body.almacen_id,
        cantidad_planeada=body.cantidad_planeada,
        creado_por=actor.id,
        idempotency_key=body.idempotency_key,
        ip=ip,
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


@router.get(
    "/trabajadores-disponibles", response_model=list[schemas.TrabajadorDisponibleOut]
)
def trabajadores_disponibles(
    area: str | None = None,
    _: Usuario = Depends(require_permission(COMPLETAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Trabajadores activos para elegir a quién imputar horas-hombre al
    completar una orden (RN-PRD-018) — vía `rrhh.queries_publicas.
    trabajadores_activos`, el contrato público de RRHH; `production` no
    conoce su ORM."""
    return rrhh_queries.trabajadores_activos(session, tenant.empresa(), area=area)


@router.get("/ordenes/{orden_id}", response_model=schemas.OrdenProduccionDetalleOut)
def ver_orden(
    orden_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_orden(session, orden_id, tenant)
    return ordenes.detalle_orden(session, orden_id)


@router.get(
    "/ordenes/{orden_id}/consumo-sugerido", response_model=schemas.ConsumoSugeridoOut
)
def ver_consumo_sugerido(
    orden_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Cuánto insumo sugiere la receta BOM para la cantidad planeada de la
    orden (RN-PRD-018), para prellenar el consumo real en vez de calcularlo
    a mano."""
    exigir_orden(session, orden_id, tenant)
    return ordenes.consumo_sugerido(session, orden_id)


@router.post(
    "/ordenes/{orden_id}/evidencia", response_model=schemas.EvidenciaOut, status_code=201
)
def adjuntar_evidencia(
    orden_id: uuid.UUID,
    body: schemas.EvidenciaCreate,
    actor: Usuario = Depends(require_permission(COMPLETAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
    ip: str | None = Depends(client_ip),
):
    """Registra la evidencia de destrucción ya subida al storage
    (RN-PRD-015). `completar` con resultado `no_conforme_desechado` exige
    que exista una antes de aceptar la merma."""
    exigir_orden(session, orden_id, tenant)
    archivo = evidencia.adjuntar_evidencia(
        session,
        orden_id,
        nombre=body.nombre,
        mime_type=body.mime_type,
        tamano_bytes=body.tamano_bytes,
        url_storage=body.url_storage,
        subido_por=actor.id,
        ip=ip,
    )
    session.commit()
    return archivo


@router.post(
    "/ordenes/{orden_id}/ordenes-hijas", response_model=schemas.OrdenProduccionOut,
    status_code=201,
)
def crear_orden_hija(
    orden_id: uuid.UUID,
    body: schemas.OrdenHijaCreate,
    actor: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
    ip: str | None = Depends(client_ip),
):
    """Crea la orden que fabrica una subreceta anidada que el consumo
    sugerido de la padre marcó `requiere_orden_hija` (RN-PRD-020): la padre
    no admite registrar su propio consumo mientras esta orden no llegue a
    `conforme`."""
    exigir_orden(session, orden_id, tenant)
    hija = ordenes.crear_orden_hija(
        session,
        orden_id,
        articulo_id=body.articulo_id,
        cantidad_planeada=body.cantidad_planeada,
        creado_por=actor.id,
        idempotency_key=body.idempotency_key,
        ip=ip,
    )
    session.commit()
    return hija


@router.post("/ordenes/{orden_id}/consumo", response_model=schemas.OrdenProduccionOut)
def registrar_consumo(
    orden_id: uuid.UUID,
    body: schemas.ConsumoCreate,
    actor: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
    ip: str | None = Depends(client_ip),
):
    exigir_orden(session, orden_id, tenant)
    orden = ordenes.registrar_consumo(
        session,
        orden_id,
        items=[it.model_dump() for it in body.items],
        actor_id=actor.id,
        idempotency_key=body.idempotency_key,
        ip=ip,
    )
    session.commit()
    return orden


@router.post("/ordenes/{orden_id}/completar", response_model=schemas.OrdenProduccionOut)
def completar_orden(
    orden_id: uuid.UUID,
    body: schemas.CompletarOrdenIn,
    actor: Usuario = Depends(require_permission(COMPLETAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
    ip: str | None = Depends(client_ip),
):
    orden_actual = exigir_orden(session, orden_id, tenant)
    almacen = session.get(Almacen, orden_actual.almacen_id)
    costo_hora_mano_obra = tarifas.costo_hora_mano_obra_de(
        session, almacen.empresa_id if almacen else None
    )
    orden = ordenes.completar_orden_produccion(
        session,
        orden_id,
        resultado=body.resultado,
        costo_hora_mano_obra=costo_hora_mano_obra,
        cantidad_producida=body.cantidad_producida,
        trabajadores=[t.model_dump() for t in body.trabajadores],
        merma_cantidad=body.merma_cantidad,
        merma_motivo=body.merma_motivo,
        fecha_vencimiento=body.fecha_vencimiento,
        lote_codigo=body.lote_codigo,
        trazabilidad=body.trazabilidad,
        registrado_por=actor.id,
        idempotency_key=body.idempotency_key,
        ip=ip,
    )
    session.commit()
    return orden


@router.post("/planes", response_model=schemas.PlanProduccionOut, status_code=201)
def crear_plan(
    body: schemas.PlanProduccionCreate,
    actor: Usuario = Depends(require_permission(PLANIFICAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
    ip: str | None = Depends(client_ip),
):
    exigir_almacen(session, body.almacen_id, tenant)
    plan = planes.crear_plan(
        session,
        almacen_id=body.almacen_id,
        fecha=body.fecha,
        turno=body.turno,
        linea_produccion=body.linea_produccion,
        creado_por=actor.id,
        ip=ip,
    )
    session.commit()
    return plan


@router.get("/planes", response_model=Pagina[schemas.PlanProduccionOut])
def listar_planes(
    almacen_id: uuid.UUID | None = None,
    fecha: date | None = None,
    estado: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return paginar(
        session,
        planes.q_planes(
            session,
            empresa_id=tenant.filtro_empresa(),
            almacen_id=almacen_id,
            fecha=fecha,
            estado=estado,
        ),
        p,
    )


@router.get("/planes/{plan_id}", response_model=schemas.PlanProduccionOut)
def ver_plan(
    plan_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_plan(session, plan_id, tenant)


@router.post(
    "/planes/{plan_id}/ordenes", response_model=schemas.OrdenProduccionOut, status_code=201
)
def agregar_orden_a_plan(
    plan_id: uuid.UUID,
    body: schemas.AgregarOrdenAPlanIn,
    actor: Usuario = Depends(require_permission(PLANIFICAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
    ip: str | None = Depends(client_ip),
):
    exigir_plan(session, plan_id, tenant)
    orden = planes.agregar_orden(
        session,
        plan_id,
        articulo_id=body.articulo_id,
        cantidad_planeada=body.cantidad_planeada,
        creado_por=actor.id,
        idempotency_key=body.idempotency_key,
        ip=ip,
    )
    session.commit()
    return orden


@router.post("/planes/{plan_id}/iniciar", response_model=schemas.PlanProduccionOut)
def iniciar_plan(
    plan_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(PLANIFICAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
    ip: str | None = Depends(client_ip),
):
    """Reserva los insumos de todas las órdenes del plan (RN-PRD-007);
    falla entero si algo no alcanza (`StockInsuficiente`, 409)."""
    exigir_plan(session, plan_id, tenant)
    plan = planes.iniciar_plan(session, plan_id, actor_id=actor.id, ip=ip)
    session.commit()
    return plan


@router.post("/planes/{plan_id}/cerrar", response_model=schemas.PlanProduccionOut)
def cerrar_plan(
    plan_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(PLANIFICAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
    ip: str | None = Depends(client_ip),
):
    """Libera lo que ninguna orden del plan llegó a consumir."""
    exigir_plan(session, plan_id, tenant)
    plan = planes.cerrar_plan(session, plan_id, actor_id=actor.id, ip=ip)
    session.commit()
    return plan


@router.post(
    "/checklists", response_model=schemas.ChecklistInocuidadTurnoOut, status_code=201
)
def crear_checklist(
    body: schemas.ChecklistInocuidadTurnoCreate,
    actor: Usuario = Depends(require_permission(VERIFICAR_INOCUIDAD)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
    ip: str | None = Depends(client_ip),
):
    """Registra el checklist de inocuidad del turno (RN-CDP-002/005):
    `estado` lo calcula el servidor, nunca lo decide quien lo llena."""
    exigir_almacen(session, body.almacen_id, tenant)
    checklist = inocuidad.crear_checklist(
        session,
        almacen_id=body.almacen_id,
        fecha=body.fecha,
        turno=body.turno,
        verificado_por=actor.id,
        bioseguridad_ok=body.bioseguridad_ok,
        superficies_ok=body.superficies_ok,
        limpieza_intermedia_ok=body.limpieza_intermedia_ok,
        equipos_frio=[eq.model_dump() for eq in body.equipos_frio],
        plaga_indicio=body.plaga_indicio,
        ip=ip,
    )
    session.commit()
    return checklist


@router.get("/checklists", response_model=Pagina[schemas.ChecklistInocuidadTurnoOut])
def listar_checklists(
    almacen_id: uuid.UUID | None = None,
    fecha: date | None = None,
    estado: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return paginar(
        session,
        inocuidad.q_checklists(
            session,
            empresa_id=tenant.filtro_empresa(),
            almacen_id=almacen_id,
            fecha=fecha,
            estado=estado,
        ),
        p,
    )


@router.get(
    "/checklists/{checklist_id}", response_model=schemas.ChecklistInocuidadTurnoOut
)
def ver_checklist(
    checklist_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_checklist(session, checklist_id, tenant)


@router.post(
    "/reportes-jornada/generar", response_model=schemas.ReporteProduccionOut
)
def generar_reporte_jornada(
    body: schemas.GenerarReporteJornadaIn,
    _: Usuario = Depends(require_permission(VISAR_REPORTE_JORNADA)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
    ip: str | None = Depends(client_ip),
):
    """Generación manual (RN-DOC-010 también la admite además del barrido
    automático de cierre): recalcula mientras el reporte no esté visado."""
    exigir_almacen(session, body.almacen_id, tenant)
    reporte = reportes_jornada.generar_reporte_jornada(
        session, almacen_id=body.almacen_id, jornada=body.fecha, ip=ip
    )
    session.commit()
    return reporte


@router.get("/reportes-jornada", response_model=Pagina[schemas.ReporteProduccionOut])
def listar_reportes_jornada(
    almacen_id: uuid.UUID | None = None,
    jornada: date | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return paginar(
        session,
        reportes_jornada.q_reportes(
            session,
            empresa_id=tenant.filtro_empresa(),
            almacen_id=almacen_id,
            jornada=jornada,
        ),
        p,
    )


@router.get(
    "/reportes-jornada/{reporte_id}", response_model=schemas.ReporteProduccionOut
)
def ver_reporte_jornada(
    reporte_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_reporte_jornada(session, reporte_id, tenant)


@router.post(
    "/reportes-jornada/{reporte_id}/visar", response_model=schemas.ReporteProduccionOut
)
def visar_reporte_jornada(
    reporte_id: uuid.UUID,
    body: schemas.VisarReporteJornadaIn,
    actor: Usuario = Depends(require_permission(VISAR_REPORTE_JORNADA)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
    ip: str | None = Depends(client_ip),
):
    """El único acto humano sobre el documento (RN-DOC-010): visa, no
    redacta."""
    exigir_reporte_jornada(session, reporte_id, tenant)
    reporte = reportes_jornada.visar_reporte(
        session, reporte_id, actor_id=actor.id, observaciones=body.observaciones, ip=ip
    )
    session.commit()
    return reporte
