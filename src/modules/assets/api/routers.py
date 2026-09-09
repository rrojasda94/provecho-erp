"""Routers FastAPI del módulo assets: activos (equipamiento/vehículo),
kilometraje y combustible, mantenimiento y documentos con vencimiento."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.assets.api import schemas
from src.modules.assets.application import (
    activos,
    combustible,
    cronograma,
    documentos,
    ordenes,
    planes,
    vehiculos,
)
from src.modules.assets.application import (
    repuestos as repuestos_uc,
)
from src.modules.assets.application.errors import NoEncontrado
from src.modules.assets.application.scope import (
    exigir_activo,
    exigir_comprobante_recibido,
    exigir_documento,
    exigir_orden_mantenimiento,
    exigir_plan,
    exigir_sujeto,
    exigir_vehiculo,
)
from src.modules.assets.domain import rules
from src.modules.assets.infrastructure.repositories import (
    ActivoRepo,
    OrdenMantenimientoRepuestoRepo,
    RepuestoCompatibilidadRepo,
    VehiculoRepo,
    q_comprobantes_disponibles,
)
from src.modules.users.api.deps import get_db, get_tenant, require_permission
from src.modules.users.infrastructure.models import Usuario
from src.shared import fechas
from src.shared.paginacion import Pagina, Paginacion, paginacion, paginar

router = APIRouter(prefix="/assets", tags=["assets"])

LEER = "assets.leer"
GESTIONAR = "assets.gestionar"
MANTENER = "assets.mantener"
DAR_BAJA = "assets.dar_baja"


# --- Serialización con derivados ---------------------------------------------
def _activo_out(session: Session, activo) -> schemas.ActivoOut:
    salida = schemas.ActivoOut.model_validate(activo)
    if activo.tipo == "vehiculo":
        vehiculo = VehiculoRepo(session).get(activo.id)
        if vehiculo is not None:
            salida.vehiculo = schemas.VehiculoOut.model_validate(vehiculo)
    return salida


def _plan_out(session: Session, plan) -> schemas.PlanMantenimientoOut:
    salida = schemas.PlanMantenimientoOut.model_validate(plan)
    activo = ActivoRepo(session).get(plan.activo_id)
    km_actual = None
    if activo is not None and activo.tipo == "vehiculo":
        vehiculo = VehiculoRepo(session).get(activo.id)
        km_actual = vehiculo.kilometraje_actual if vehiculo else None
    if activo is not None:
        estado = planes.estado_de(plan, activo, km_actual)
        salida.estado = estado.estado
        salida.proxima_fecha = estado.proxima_fecha
        salida.proximo_km = estado.proximo_km
    return salida


def _orden_out(session: Session, orden) -> schemas.OrdenMantenimientoOut:
    salida = schemas.OrdenMantenimientoOut.model_validate(orden)
    salida.repuestos = [
        schemas.RepuestoUsadoOut.model_validate(r)
        for r in OrdenMantenimientoRepuestoRepo(session).list_de_orden(orden.id)
    ]
    return salida


def _documento_out(documento) -> schemas.DocumentoVigenciaOut:
    salida = schemas.DocumentoVigenciaOut.model_validate(documento)
    estado = rules.estado_documento(
        hoy=fechas.hoy(),
        fecha_vencimiento=documento.fecha_vencimiento,
        dias_aviso=documento.dias_aviso,
        renovado=documento.renovado_por_id is not None,
    )
    salida.estado = estado.estado
    return salida


# --- Activos ------------------------------------------------------------------
@router.post("/activos", response_model=schemas.ActivoOut, status_code=201)
def crear_activo(
    body: schemas.ActivoCreate,
    actor: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    empresa_id = tenant.empresa()
    activo = activos.crear_activo(
        session, empresa_id=empresa_id, creado_por=actor.id, **body.model_dump()
    )
    session.commit()
    return _activo_out(session, activo)


@router.get("/activos", response_model=Pagina[schemas.ActivoOut])
def listar_activos(
    tipo: schemas.TipoActivo | None = None,
    sucursal_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    pagina = paginar(
        session,
        activos.q_activos(session, tenant.filtro_empresa(), tipo=tipo, sucursal_id=sucursal_id),
        p,
    )
    pagina["items"] = [_activo_out(session, a) for a in pagina["items"]]
    return pagina


@router.get("/activos/{activo_id}", response_model=schemas.ActivoOut)
def ver_activo(
    activo_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    activo = exigir_activo(session, activo_id, tenant)
    return _activo_out(session, activo)


@router.patch("/activos/{activo_id}", response_model=schemas.ActivoOut)
def editar_activo(
    activo_id: uuid.UUID,
    body: schemas.ActivoUpdate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_activo(session, activo_id, tenant)
    activo = activos.editar_activo(session, activo_id, **body.model_dump())
    session.commit()
    return _activo_out(session, activo)


@router.post("/activos/{activo_id}/baja", response_model=schemas.ActivoOut)
def dar_baja_activo(
    activo_id: uuid.UUID,
    body: schemas.ActivoBaja,
    actor: Usuario = Depends(require_permission(DAR_BAJA)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_activo(session, activo_id, tenant)
    activo = activos.dar_baja_activo(session, activo_id, actor_id=actor.id, motivo=body.motivo)
    session.commit()
    return _activo_out(session, activo)


# --- Kilometraje y combustible -------------------------------------------------
@router.post(
    "/activos/{activo_id}/lecturas-odometro",
    response_model=schemas.LecturaOdometroOut,
    status_code=201,
)
def registrar_lectura_odometro(
    activo_id: uuid.UUID,
    body: schemas.LecturaOdometroCreate,
    actor: Usuario = Depends(require_permission(MANTENER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    vehiculo = exigir_vehiculo(session, activo_id, tenant)
    lectura = vehiculos.registrar_lectura(
        session,
        vehiculo,
        km=body.km,
        fecha=body.fecha,
        origen="manual",
        registrado_por=actor.id,
        nota=body.nota,
    )
    session.commit()
    return lectura


@router.get(
    "/activos/{activo_id}/lecturas-odometro",
    response_model=list[schemas.LecturaOdometroOut],
)
def listar_lecturas_odometro(
    activo_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_vehiculo(session, activo_id, tenant)
    return list(session.scalars(vehiculos.q_lecturas(session, activo_id)))


@router.post(
    "/activos/{activo_id}/cargas-combustible",
    response_model=schemas.CargaCombustibleOut,
    status_code=201,
)
def registrar_carga_combustible(
    activo_id: uuid.UUID,
    body: schemas.CargaCombustibleCreate,
    actor: Usuario = Depends(require_permission(MANTENER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    vehiculo = exigir_vehiculo(session, activo_id, tenant)
    exigir_comprobante_recibido(session, body.comprobante_id, tenant)
    carga = combustible.registrar_carga(
        session,
        vehiculo,
        comprobante_id=body.comprobante_id,
        fecha=body.fecha,
        galones=body.galones,
        monto=body.monto,
        km_odometro=body.km_odometro,
        registrado_por=actor.id,
        tipo_combustible=body.tipo_combustible,
    )
    session.commit()
    return carga


@router.get(
    "/activos/{activo_id}/cargas-combustible",
    response_model=list[schemas.CargaCombustibleOut],
)
def listar_cargas_combustible(
    activo_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_vehiculo(session, activo_id, tenant)
    return list(session.scalars(combustible.q_cargas(session, activo_id)))


@router.get("/activos/{activo_id}/consumo", response_model=schemas.ResumenConsumoOut)
def ver_consumo(
    activo_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_vehiculo(session, activo_id, tenant)
    return combustible.resumen_consumo(session, activo_id)


@router.get(
    "/comprobantes-disponibles",
    response_model=list[schemas.ComprobanteDisponibleOut],
)
def listar_comprobantes_disponibles(
    desde: date | None = None,
    hasta: date | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Comprobantes recibidos de la empresa que aún no sustentan una carga de
    combustible ni una orden de mantenimiento — lo que la pantalla de alta
    ofrece para elegir."""
    empresa_id = tenant.empresa()
    return list(session.scalars(q_comprobantes_disponibles(empresa_id, desde=desde, hasta=hasta)))


# --- Planes de mantenimiento ---------------------------------------------------
@router.post("/planes", response_model=schemas.PlanMantenimientoOut, status_code=201)
def crear_plan(
    body: schemas.PlanMantenimientoCreate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_activo(session, body.activo_id, tenant)
    plan = planes.crear_plan(session, **body.model_dump())
    session.commit()
    return _plan_out(session, plan)


@router.get("/planes", response_model=list[schemas.PlanMantenimientoOut])
def listar_planes(
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    filas = list(session.scalars(planes.q_planes(session, tenant.filtro_empresa())))
    return [_plan_out(session, p) for p in filas]


@router.get("/activos/{activo_id}/planes", response_model=list[schemas.PlanMantenimientoOut])
def listar_planes_de_activo(
    activo_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_activo(session, activo_id, tenant)
    filas = list(session.scalars(planes.q_de_activo(session, activo_id)))
    return [_plan_out(session, p) for p in filas]


@router.patch("/planes/{plan_id}", response_model=schemas.PlanMantenimientoOut)
def editar_plan(
    plan_id: uuid.UUID,
    body: schemas.PlanMantenimientoUpdate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_plan(session, plan_id, tenant)
    plan = planes.editar_plan(session, plan_id, **body.model_dump())
    session.commit()
    return _plan_out(session, plan)


# --- Órdenes de mantenimiento ---------------------------------------------------
@router.post(
    "/ordenes-mantenimiento", response_model=schemas.OrdenMantenimientoOut, status_code=201
)
def crear_orden_mantenimiento(
    body: schemas.OrdenMantenimientoCreate,
    actor: Usuario = Depends(require_permission(MANTENER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_activo(session, body.activo_id, tenant)
    orden = ordenes.crear_orden(session, reportado_por=actor.id, **body.model_dump())
    session.commit()
    return _orden_out(session, orden)


@router.get("/ordenes-mantenimiento", response_model=Pagina[schemas.OrdenMantenimientoOut])
def listar_ordenes_mantenimiento(
    estado: schemas.EstadoOrdenMantenimiento | None = None,
    activo_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    if activo_id is not None:
        exigir_activo(session, activo_id, tenant)
    pagina = paginar(
        session,
        ordenes.q_ordenes(session, tenant.filtro_empresa(), estado=estado, activo_id=activo_id),
        p,
    )
    pagina["items"] = [_orden_out(session, o) for o in pagina["items"]]
    return pagina


@router.get("/ordenes-mantenimiento/{orden_id}", response_model=schemas.OrdenMantenimientoOut)
def ver_orden_mantenimiento(
    orden_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return _orden_out(session, exigir_orden_mantenimiento(session, orden_id, tenant))


@router.post(
    "/ordenes-mantenimiento/{orden_id}/iniciar",
    response_model=schemas.OrdenMantenimientoOut,
)
def iniciar_orden_mantenimiento(
    orden_id: uuid.UUID,
    _: Usuario = Depends(require_permission(MANTENER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    orden = exigir_orden_mantenimiento(session, orden_id, tenant)
    ordenes.iniciar_orden(session, orden)
    session.commit()
    return _orden_out(session, orden)


@router.post(
    "/ordenes-mantenimiento/{orden_id}/realizar",
    response_model=schemas.OrdenMantenimientoOut,
)
def realizar_orden_mantenimiento(
    orden_id: uuid.UUID,
    body: schemas.OrdenMantenimientoRealizar,
    actor: Usuario = Depends(require_permission(MANTENER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    orden = exigir_orden_mantenimiento(session, orden_id, tenant)
    if body.comprobante_id is not None:
        exigir_comprobante_recibido(session, body.comprobante_id, tenant)
    ordenes.realizar_orden(session, orden, actor_id=actor.id, **body.model_dump())
    session.commit()
    return _orden_out(session, orden)


@router.post(
    "/ordenes-mantenimiento/{orden_id}/cancelar",
    response_model=schemas.OrdenMantenimientoOut,
)
def cancelar_orden_mantenimiento(
    orden_id: uuid.UUID,
    body: schemas.OrdenMantenimientoCancelar,
    actor: Usuario = Depends(require_permission(MANTENER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    orden = exigir_orden_mantenimiento(session, orden_id, tenant)
    ordenes.cancelar_orden(session, orden, actor_id=actor.id, motivo=body.motivo)
    session.commit()
    return _orden_out(session, orden)


# --- Repuestos compatibles -------------------------------------------------------
@router.post(
    "/activos/{activo_id}/repuestos-compatibles",
    response_model=schemas.RepuestoCompatibleOut,
    status_code=201,
)
def agregar_repuesto_compatible(
    activo_id: uuid.UUID,
    body: schemas.RepuestoCompatibleCreate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_activo(session, activo_id, tenant)
    repuesto = repuestos_uc.agregar_compatible(session, activo_id=activo_id, **body.model_dump())
    session.commit()
    return repuesto


@router.get(
    "/activos/{activo_id}/repuestos-compatibles",
    response_model=list[schemas.RepuestoCompatibleOut],
)
def listar_repuestos_compatibles(
    activo_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_activo(session, activo_id, tenant)
    return repuestos_uc.q_de_activo(session, activo_id)


@router.delete(
    "/activos/{activo_id}/repuestos-compatibles/{repuesto_id}",
    status_code=204,
)
def quitar_repuesto_compatible(
    activo_id: uuid.UUID,
    repuesto_id: uuid.UUID,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_activo(session, activo_id, tenant)
    repuesto = RepuestoCompatibilidadRepo(session).get(repuesto_id)
    if repuesto is None or repuesto.activo_id != activo_id:
        raise NoEncontrado("repuesto compatible no encontrado")
    repuestos_uc.quitar_compatible(session, repuesto)
    session.commit()


# --- Documentos con vencimiento -------------------------------------------------
@router.post("/documentos", response_model=schemas.DocumentoVigenciaOut, status_code=201)
def crear_documento(
    body: schemas.DocumentoVigenciaCreate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    empresa_id = exigir_sujeto(session, body.sujeto_tipo, body.sujeto_id, tenant)
    documento = documentos.crear_documento(session, empresa_id=empresa_id, **body.model_dump())
    session.commit()
    return _documento_out(documento)


@router.get("/documentos", response_model=list[schemas.DocumentoVigenciaOut])
def listar_documentos(
    sujeto_tipo: schemas.SujetoDocumento | None = None,
    sujeto_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    filas = list(
        session.scalars(
            documentos.q_documentos(
                session, tenant.filtro_empresa(), sujeto_tipo=sujeto_tipo, sujeto_id=sujeto_id
            )
        )
    )
    return [_documento_out(d) for d in filas]


@router.get("/documentos/{documento_id}", response_model=schemas.DocumentoVigenciaOut)
def ver_documento(
    documento_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    documento = exigir_documento(session, documento_id, tenant)
    return _documento_out(documento)


@router.patch("/documentos/{documento_id}", response_model=schemas.DocumentoVigenciaOut)
def editar_documento(
    documento_id: uuid.UUID,
    body: schemas.DocumentoVigenciaUpdate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_documento(session, documento_id, tenant)
    documento = documentos.editar_documento(session, documento_id, **body.model_dump())
    session.commit()
    return _documento_out(documento)


@router.post(
    "/documentos/{documento_id}/renovar",
    response_model=schemas.DocumentoVigenciaOut,
    status_code=201,
)
def renovar_documento(
    documento_id: uuid.UUID,
    body: schemas.DocumentoVigenciaRenovar,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    documento = exigir_documento(session, documento_id, tenant)
    nuevo = documentos.renovar_documento(session, documento, **body.model_dump())
    session.commit()
    return _documento_out(nuevo)


@router.post(
    "/documentos/{documento_id}/adjuntos/presign-upload",
    response_model=schemas.PresignAdjuntoOut,
)
def presignar_adjunto_documento(
    documento_id: uuid.UUID,
    body: schemas.PresignAdjuntoIn,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_documento(session, documento_id, tenant)
    return documentos.presignar_adjunto(session, documento_id, **body.model_dump())


@router.post(
    "/documentos/{documento_id}/adjuntos",
    response_model=schemas.ArchivoOut,
    status_code=201,
)
def adjuntar_documento(
    documento_id: uuid.UUID,
    body: schemas.ArchivoAdjuntoCreate,
    actor: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_documento(session, documento_id, tenant)
    archivo = documentos.adjuntar(session, documento_id, subido_por=actor.id, **body.model_dump())
    session.commit()
    return archivo


@router.get("/documentos/{documento_id}/adjuntos", response_model=list[schemas.ArchivoOut])
def listar_adjuntos_documento(
    documento_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_documento(session, documento_id, tenant)
    return documentos.listar_adjuntos(session, documento_id)


# --- Cronograma -----------------------------------------------------------------
@router.get("/cronograma", response_model=list[schemas.CronogramaItemOut])
def ver_cronograma(
    dias: int = 90,
    sucursal_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return cronograma.agenda(session, tenant.filtro_empresa(), dias=dias, sucursal_id=sucursal_id)
