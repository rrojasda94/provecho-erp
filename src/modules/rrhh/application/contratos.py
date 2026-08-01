"""Casos de uso de `contrato_laboral`: crear (borrador) → firmar → finalizar
(RN-RRHH-012, RN-CTR-004: nadie trabaja sin contrato firmado, todo contrato
se registra en el ERP)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.rrhh.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.rrhh.domain import rules
from src.modules.rrhh.infrastructure.models import ContratoLaboral
from src.modules.rrhh.infrastructure.repositories import ContratoLaboralRepo, TrabajadorRepo


def crear_contrato_laboral(
    session: Session,
    *,
    trabajador_id: uuid.UUID,
    modalidad: str,
    jornada_horas_semana: Decimal,
    remuneracion: Decimal,
    fecha_inicio: date,
    fecha_fin: date | None = None,
) -> ContratoLaboral:
    if modalidad not in rules.MODALIDADES_CONTRATO:
        raise ReglaNegocio(f"modalidad inválida: {modalidad}")
    if modalidad != "indeterminado" and fecha_fin is None:
        raise ReglaNegocio("modalidad a plazo requiere fecha_fin")
    if TrabajadorRepo(session).get(trabajador_id) is None:
        raise NoEncontrado(f"trabajador {trabajador_id} no encontrado")

    return ContratoLaboralRepo(session).add(
        ContratoLaboral(
            trabajador_id=trabajador_id,
            modalidad=modalidad,
            jornada_horas_semana=jornada_horas_semana,
            remuneracion=remuneracion,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
    )


def firmar_contrato_laboral(
    session: Session, contrato_id: uuid.UUID, *, fecha_firma: date
) -> ContratoLaboral:
    contrato = ContratoLaboralRepo(session).get(contrato_id)
    if contrato is None:
        raise NoEncontrado("contrato no encontrado")
    if not rules.puede_firmar_contrato(contrato.estado):
        raise Conflicto(f"contrato está {contrato.estado}; no admite firma")
    contrato.estado = "firmado"
    contrato.fecha_firma = fecha_firma
    event_bus.publish(
        "rrhh.contrato_laboral_firmado",
        {
            "contrato_laboral_id": str(contrato.id),
            "trabajador_id": str(contrato.trabajador_id),
            "fecha_firma": fecha_firma.isoformat(),
        },
        session=session,
    )
    return contrato


def finalizar_contrato_laboral(session: Session, contrato_id: uuid.UUID) -> ContratoLaboral:
    contrato = ContratoLaboralRepo(session).get(contrato_id)
    if contrato is None:
        raise NoEncontrado("contrato no encontrado")
    if not rules.puede_finalizar_contrato(contrato.estado):
        raise Conflicto(f"contrato está {contrato.estado}; no admite finalización")
    contrato.estado = "finalizado"
    return contrato


def listar_contratos_de_trabajador(
    session: Session, trabajador_id: uuid.UUID
) -> list[ContratoLaboral]:
    return ContratoLaboralRepo(session).list_por_trabajador(trabajador_id)
