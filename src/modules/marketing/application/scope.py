"""Validación de alcance de tenant sobre recursos de marketing (ADR-004).

`campana` lleva `empresa_id` propio. Todo lo que cuelga de ella (pieza,
lead, implementación de material) se escopa por su campaña. La encuesta se
escopa por la sucursal de su venta, vía el contrato público de `sales`.
"""

import uuid

from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.marketing.application.errors import NoEncontrado
from src.modules.marketing.infrastructure.models import (
    Campana,
    EncuestaPlantilla,
    EncuestaSatisfaccion,
    EvaluacionAgencia,
    Lead,
    PiezaContenido,
)
from src.modules.sales.application.queries_publicas import venta_para_encuesta
from src.modules.users.infrastructure.models import Sucursal


def exigir_campana(session: Session, campana_id: uuid.UUID, tenant: Tenant) -> Campana:
    campana = session.get(Campana, campana_id)
    if campana is None or campana.deleted_at is not None:
        raise NoEncontrado("campaña no encontrada")
    tenant.exigir_empresa(campana.empresa_id)
    return campana


def exigir_lead(session: Session, lead_id: uuid.UUID, tenant: Tenant) -> Lead:
    lead = session.get(Lead, lead_id)
    if lead is None:
        raise NoEncontrado("lead no encontrado")
    exigir_campana(session, lead.campana_id, tenant)
    return lead


def exigir_pieza(session: Session, pieza_id: uuid.UUID, tenant: Tenant) -> PiezaContenido:
    pieza = session.get(PiezaContenido, pieza_id)
    if pieza is None:
        raise NoEncontrado("pieza de contenido no encontrada")
    if pieza.campana_id is not None:
        exigir_campana(session, pieza.campana_id, tenant)
    return pieza


def exigir_sucursal(session: Session, sucursal_id: uuid.UUID, tenant: Tenant) -> Sucursal:
    sucursal = session.get(Sucursal, sucursal_id)
    if sucursal is None or sucursal.deleted_at is not None:
        raise NoEncontrado("sucursal no encontrada")
    tenant.exigir_empresa(sucursal.empresa_id)
    tenant.exigir_sucursal(sucursal.id)
    return sucursal


def exigir_plantilla(
    session: Session, plantilla_id: uuid.UUID, tenant: Tenant
) -> EncuestaPlantilla:
    plantilla = session.get(EncuestaPlantilla, plantilla_id)
    if plantilla is None or plantilla.deleted_at is not None:
        raise NoEncontrado("plantilla de encuesta no encontrada")
    tenant.exigir_empresa(plantilla.empresa_id)
    return plantilla


def exigir_evaluacion(
    session: Session, evaluacion_id: uuid.UUID, tenant: Tenant
) -> EvaluacionAgencia:
    evaluacion = session.get(EvaluacionAgencia, evaluacion_id)
    if evaluacion is None:
        raise NoEncontrado("evaluación de agencia no encontrada")
    exigir_campana(session, evaluacion.campana_id, tenant)
    return evaluacion


def exigir_encuesta(
    session: Session, encuesta_id: uuid.UUID, tenant: Tenant
) -> EncuestaSatisfaccion:
    encuesta = session.get(EncuestaSatisfaccion, encuesta_id)
    if encuesta is None:
        raise NoEncontrado("encuesta no encontrada")
    venta = venta_para_encuesta(session, encuesta.venta_id)
    if venta is None:
        raise NoEncontrado("venta de la encuesta no encontrada")
    exigir_sucursal(session, venta["sucursal_id"], tenant)
    return encuesta
