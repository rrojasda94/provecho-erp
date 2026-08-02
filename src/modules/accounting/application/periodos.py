"""Casos de uso: periodo contable. Abrir es idempotente (mismo mes/año
devuelve el existente); cerrar es definitivo salvo asiento inverso
(RN-CTB-002)."""

import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.accounting.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.accounting.domain import rules
from src.modules.accounting.infrastructure.models import PeriodoContable
from src.modules.accounting.infrastructure.repositories import PeriodoContableRepo


def abrir_periodo(
    session: Session, *, empresa_id: uuid.UUID, anio: int, mes: int
) -> PeriodoContable:
    if not 1 <= mes <= 12:
        raise ReglaNegocio(f"mes inválido: {mes}")
    repo = PeriodoContableRepo(session)
    existente = repo.get_by_anio_mes(empresa_id, anio, mes)
    if existente is not None:
        return existente
    return repo.add(PeriodoContable(empresa_id=empresa_id, anio=anio, mes=mes, estado="abierto"))


def listar_periodos(
    session: Session, empresa_id: uuid.UUID | None = None
) -> list[PeriodoContable]:
    return PeriodoContableRepo(session).list(empresa_id)


def cerrar_periodo(
    session: Session, periodo_id: uuid.UUID, *, cerrado_por: uuid.UUID
) -> PeriodoContable:
    periodo = PeriodoContableRepo(session).get(periodo_id)
    if periodo is None:
        raise NoEncontrado("periodo contable no encontrado")
    if not rules.puede_cerrar(periodo.estado):
        raise Conflicto(f"el periodo ya está {periodo.estado}")
    periodo.estado = "cerrado"
    periodo.cerrado_por = cerrado_por
    periodo.fecha_cierre = datetime.now()
    event_bus.publish(
        "accounting.periodo_cerrado",
        {"periodo_id": str(periodo.id), "fecha_cierre": periodo.fecha_cierre.isoformat()},
        session=session,
    )
    return periodo


def periodo_de_fecha(
    session: Session, empresa_id: uuid.UUID, fecha: date
) -> PeriodoContable | None:
    return PeriodoContableRepo(session).get_by_anio_mes(empresa_id, fecha.year, fecha.month)
