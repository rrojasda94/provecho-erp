"""Validación de alcance de tenant sobre recursos de supervision (ADR-004)."""

import uuid

from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.supervision.application.errors import NoEncontrado
from src.modules.supervision.infrastructure.models import (
    CategoriaTarea,
    InformeDiario,
    TareaInstancia,
    TareaPlantilla,
)
from src.modules.users.infrastructure.models import Sucursal


def exigir_sucursal(session: Session, sucursal_id: uuid.UUID, tenant: Tenant) -> Sucursal:
    sucursal = session.get(Sucursal, sucursal_id)
    if sucursal is None or sucursal.deleted_at is not None:
        raise NoEncontrado("sucursal no encontrada")
    tenant.exigir_empresa(sucursal.empresa_id)
    return sucursal


def exigir_categoria(
    session: Session, categoria_id: uuid.UUID, tenant: Tenant
) -> CategoriaTarea:
    categoria = session.get(CategoriaTarea, categoria_id)
    if categoria is None:
        raise NoEncontrado("categoría no encontrada")
    tenant.exigir_empresa(categoria.empresa_id)
    return categoria


def exigir_plantilla(
    session: Session, plantilla_id: uuid.UUID, tenant: Tenant
) -> TareaPlantilla:
    plantilla = session.get(TareaPlantilla, plantilla_id)
    if plantilla is None:
        raise NoEncontrado("plantilla no encontrada")
    tenant.exigir_empresa(plantilla.empresa_id)
    return plantilla


def exigir_instancia(
    session: Session, instancia_id: uuid.UUID, tenant: Tenant
) -> TareaInstancia:
    instancia = session.get(TareaInstancia, instancia_id)
    if instancia is None:
        raise NoEncontrado("tarea no encontrada")
    exigir_sucursal(session, instancia.sucursal_id, tenant)
    return instancia


def exigir_informe(session: Session, informe_id: uuid.UUID, tenant: Tenant) -> InformeDiario:
    informe = session.get(InformeDiario, informe_id)
    if informe is None:
        raise NoEncontrado("informe no encontrado")
    exigir_sucursal(session, informe.sucursal_id, tenant)
    return informe
