"""Validación de alcance de tenant sobre recursos de `reports` (ADR-004).

Áreas y reglas llevan su `empresa_id`; miembros y destinatarios heredan el
alcance de su padre. El cliente nunca elige la empresa: se deriva del JWT.
"""

import uuid

from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.reports.application.errors import NoEncontrado
from src.modules.reports.infrastructure.models import (
    Area,
    AreaMiembro,
    ReglaDistribucion,
    ReporteEmitido,
    ReporteEscalamiento,
)


def exigir_area(session: Session, area_id: uuid.UUID, tenant: Tenant) -> Area:
    area = session.get(Area, area_id)
    if area is None:
        raise NoEncontrado("área no encontrada")
    tenant.exigir_empresa(area.empresa_id)
    return area


def exigir_miembro(
    session: Session, miembro_id: uuid.UUID, tenant: Tenant
) -> AreaMiembro:
    miembro = session.get(AreaMiembro, miembro_id)
    if miembro is None:
        raise NoEncontrado("miembro no encontrado")
    exigir_area(session, miembro.area_id, tenant)
    return miembro


def exigir_regla(
    session: Session, regla_id: uuid.UUID, tenant: Tenant
) -> ReglaDistribucion:
    regla = session.get(ReglaDistribucion, regla_id)
    if regla is None:
        raise NoEncontrado("regla no encontrada")
    tenant.exigir_empresa(regla.empresa_id)
    return regla


def exigir_escalamiento(
    session: Session, escalamiento_id: uuid.UUID, tenant: Tenant
) -> ReporteEscalamiento:
    escalamiento = session.get(ReporteEscalamiento, escalamiento_id)
    if escalamiento is None:
        raise NoEncontrado("escalamiento no encontrado")
    # `empresa_id` es NOT NULL acá (RN-REP-011): un reporte que no se pudo
    # atribuir no se escala, así que no hay caso de superusuario que resolver.
    tenant.exigir_empresa(escalamiento.empresa_id)
    return escalamiento


def exigir_reporte(
    session: Session, reporte_id: uuid.UUID, tenant: Tenant
) -> ReporteEmitido:
    reporte = session.get(ReporteEmitido, reporte_id)
    if reporte is None:
        raise NoEncontrado("reporte no encontrado")
    # Un reporte sin empresa (el hecho no se pudo atribuir) solo lo alcanza
    # el superusuario: adivinarle un tenant sería mostrarle a una empresa lo
    # que pasó en otra. Mismo criterio que ADR-031 para `audit_log`.
    if reporte.empresa_id is None:
        if not tenant.superusuario:
            raise NoEncontrado("reporte no encontrado")
        return reporte
    tenant.exigir_empresa(reporte.empresa_id)
    return reporte
