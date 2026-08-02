"""Routers FastAPI del módulo marketing: campaña, contenido, lead y encuesta."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.marketing.api import schemas
from src.modules.marketing.application import campanas, contenido, encuestas, leads
from src.modules.marketing.application.errors import (
    Conflicto,
    MarketingError,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.marketing.application.scope import (
    exigir_campana,
    exigir_encuesta,
    exigir_lead,
    exigir_pieza,
    exigir_sucursal,
)
from src.modules.marketing.infrastructure.repositories import CampanaRepo, LeadRepo
from src.modules.sales.application.queries_publicas import venta_para_encuesta
from src.modules.users.api.deps import get_db, get_tenant, require_permission
from src.modules.users.infrastructure.models import Usuario

router = APIRouter(prefix="/marketing", tags=["marketing"])

LEER = "marketing.leer"
CAMPANA_GESTIONAR = "marketing.campana_gestionar"
CAMPANA_APROBAR = "marketing.campana_aprobar"
CONTENIDO_GESTIONAR = "marketing.contenido_gestionar"
LEAD_GESTIONAR = "marketing.lead_gestionar"
ENCUESTA_GESTIONAR = "marketing.encuesta_gestionar"

_HTTP_STATUS: dict[type[MarketingError], int] = {
    NoEncontrado: status.HTTP_404_NOT_FOUND,
    Conflicto: status.HTTP_409_CONFLICT,
    ReglaNegocio: status.HTTP_409_CONFLICT,
}


def _http(err: MarketingError) -> HTTPException:
    return HTTPException(_HTTP_STATUS.get(type(err), 400), str(err))


# --- Campaña ---------------------------------------------------------------


@router.post("/campanas", response_model=schemas.CampanaOut, status_code=201)
def crear_campana(
    body: schemas.CampanaCreate,
    actor: Usuario = Depends(require_permission(CAMPANA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        campana = campanas.crear_campana(
            session,
            empresa_id=tenant.empresa(body.empresa_id),
            marca_id=body.marca_id,
            nombre=body.nombre,
            tipo=body.tipo,
            canal=body.canal,
            objetivo=body.objetivo,
            publico_objetivo=body.publico_objetivo,
            presupuesto=body.presupuesto,
            kpi=body.kpi,
            creado_por=actor.id,
            idempotency_key=body.idempotency_key,
        )
    except (NoEncontrado, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return campana


@router.get("/campanas", response_model=list[schemas.CampanaOut])
def listar_campanas(
    estado: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return CampanaRepo(session).listar(tenant.filtro_empresa(), estado=estado)


@router.get("/campanas/{campana_id}", response_model=schemas.CampanaOut)
def ver_campana(
    campana_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        return exigir_campana(session, campana_id, tenant)
    except NoEncontrado as e:
        raise _http(e) from e


@router.patch("/campanas/{campana_id}/brief", response_model=schemas.CampanaOut)
def completar_brief(
    campana_id: uuid.UUID,
    body: schemas.BriefUpdate,
    _: Usuario = Depends(require_permission(CAMPANA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_campana(session, campana_id, tenant)
        campana = campanas.completar_brief(
            session,
            campana_id,
            objetivo=body.objetivo,
            publico_objetivo=body.publico_objetivo,
            presupuesto=body.presupuesto,
            kpi=body.kpi,
        )
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return campana


@router.post("/campanas/{campana_id}/aprobacion", response_model=schemas.CampanaOut)
def aprobar_campana(
    campana_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(CAMPANA_APROBAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_campana(session, campana_id, tenant)
        campana = campanas.aprobar_campana(session, campana_id, aprobada_por=actor.id)
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return campana


@router.post("/campanas/{campana_id}/lanzamiento", response_model=schemas.CampanaOut)
def lanzar_campana(
    campana_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CAMPANA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_campana(session, campana_id, tenant)
        campana = campanas.lanzar_campana(session, campana_id)
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return campana


@router.post("/campanas/{campana_id}/cierre", response_model=schemas.CampanaOut)
def cerrar_campana(
    campana_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CAMPANA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_campana(session, campana_id, tenant)
        campana = campanas.cerrar_campana(session, campana_id)
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return campana


@router.post(
    "/campanas/{campana_id}/implementaciones",
    response_model=schemas.ImplementacionOut,
    status_code=201,
)
def registrar_implementacion(
    campana_id: uuid.UUID,
    body: schemas.ImplementacionCreate,
    actor: Usuario = Depends(require_permission(CAMPANA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_campana(session, campana_id, tenant)
        exigir_sucursal(session, body.sucursal_id, tenant)
        registro = campanas.registrar_implementacion_material(
            session,
            campana_id,
            sucursal_id=body.sucursal_id,
            verificado_por=actor.id,
            completa=body.completa,
            incidencia=body.incidencia,
            fecha=body.fecha,
        )
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return registro


# --- Contenido -------------------------------------------------------------


@router.post("/piezas", response_model=schemas.PiezaOut, status_code=201)
def planificar_pieza(
    body: schemas.PiezaCreate,
    actor: Usuario = Depends(require_permission(CONTENIDO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        if body.campana_id is not None:
            exigir_campana(session, body.campana_id, tenant)
        pieza = contenido.planificar_pieza(
            session,
            marca_id=body.marca_id,
            titulo=body.titulo,
            canal=body.canal,
            fecha_publicacion=body.fecha_publicacion,
            campana_id=body.campana_id,
            pertinente_marca=body.pertinente_marca,
            uso_marca_validado=body.uso_marca_validado,
            creado_por=actor.id,
        )
    except NoEncontrado as e:
        raise _http(e) from e
    session.commit()
    return pieza


@router.patch("/piezas/{pieza_id}/validacion", response_model=schemas.PiezaOut)
def validar_pieza(
    pieza_id: uuid.UUID,
    body: schemas.PiezaValidar,
    _: Usuario = Depends(require_permission(CONTENIDO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_pieza(session, pieza_id, tenant)
        pieza = contenido.validar_pieza(
            session,
            pieza_id,
            pertinente_marca=body.pertinente_marca,
            uso_marca_validado=body.uso_marca_validado,
        )
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return pieza


@router.post("/piezas/{pieza_id}/publicacion", response_model=schemas.PiezaOut)
def publicar_pieza(
    pieza_id: uuid.UUID,
    body: schemas.PiezaPublicar,
    _: Usuario = Depends(require_permission(CONTENIDO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_pieza(session, pieza_id, tenant)
        pieza = contenido.publicar_pieza(session, pieza_id, metricas=body.metricas)
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return pieza


@router.post("/piezas/{pieza_id}/descarte", response_model=schemas.PiezaOut)
def descartar_pieza(
    pieza_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CONTENIDO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_pieza(session, pieza_id, tenant)
        pieza = contenido.descartar_pieza(session, pieza_id)
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return pieza


# --- Lead ------------------------------------------------------------------


@router.post("/leads", response_model=schemas.LeadOut, status_code=201)
def registrar_lead(
    body: schemas.LeadCreate,
    _: Usuario = Depends(require_permission(LEAD_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_campana(session, body.campana_id, tenant)
        lead = leads.registrar_lead(
            session,
            campana_id=body.campana_id,
            canal=body.canal,
            tipo=body.tipo,
            contacto=body.contacto,
            cliente_id=body.cliente_id,
            idempotency_key=body.idempotency_key,
        )
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return lead


@router.get("/campanas/{campana_id}/leads", response_model=list[schemas.LeadOut])
def listar_leads(
    campana_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_campana(session, campana_id, tenant)
    except NoEncontrado as e:
        raise _http(e) from e
    return LeadRepo(session).de_campana(campana_id)


@router.post("/leads/{lead_id}/atribucion", response_model=schemas.LeadOut)
def atribuir_lead(
    lead_id: uuid.UUID,
    body: schemas.LeadAtribuir,
    _: Usuario = Depends(require_permission(LEAD_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_lead(session, lead_id, tenant)
        venta = venta_para_encuesta(session, body.venta_id)
        if venta is None:
            raise NoEncontrado("venta no encontrada")
        exigir_sucursal(session, venta["sucursal_id"], tenant)
        lead = leads.atribuir_venta(session, lead_id, venta_id=body.venta_id)
    except (NoEncontrado, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return lead


# --- Encuesta de satisfacción ----------------------------------------------


@router.post("/encuestas", response_model=schemas.EncuestaOut, status_code=201)
def enviar_encuesta(
    body: schemas.EncuestaCreate,
    actor: Usuario = Depends(require_permission(ENCUESTA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        venta = venta_para_encuesta(session, body.venta_id)
        if venta is None:
            raise NoEncontrado("venta no encontrada")
        exigir_sucursal(session, venta["sucursal_id"], tenant)
        encuesta = encuestas.enviar_encuesta(
            session, venta_id=body.venta_id, canal=body.canal, enviada_por=actor.id
        )
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return encuesta


@router.post("/encuestas/{encuesta_id}/respuesta", response_model=schemas.EncuestaOut)
def responder_encuesta(
    encuesta_id: uuid.UUID,
    body: schemas.EncuestaRespuesta,
    _: Usuario = Depends(require_permission(ENCUESTA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_encuesta(session, encuesta_id, tenant)
        encuesta = encuestas.registrar_respuesta(
            session, encuesta_id, puntaje=body.puntaje, comentario=body.comentario
        )
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return encuesta


@router.post("/encuestas/{encuesta_id}/expiracion", response_model=schemas.EncuestaOut)
def expirar_encuesta(
    encuesta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(ENCUESTA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_encuesta(session, encuesta_id, tenant)
        encuesta = encuestas.expirar_encuesta(session, encuesta_id)
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return encuesta
