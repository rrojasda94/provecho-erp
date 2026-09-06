"""Casos de uso: periodo contable. Abrir es idempotente (mismo mes/año
devuelve el existente); cerrar es definitivo salvo asiento inverso
(RN-CTB-002)."""

import uuid
from datetime import UTC, date, datetime

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


def listar_periodos(session: Session, empresa_id: uuid.UUID | None = None) -> list[PeriodoContable]:
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
    periodo.fecha_cierre = datetime.now(UTC)
    event_bus.publish(
        "accounting.periodo_cerrado",
        {"periodo_id": str(periodo.id), "fecha_cierre": periodo.fecha_cierre.isoformat()},
        session=session,
    )
    return periodo


def periodo_de_fecha(
    session: Session, empresa_id: uuid.UUID, fecha: date
) -> PeriodoContable | None:
    """Lookup puro: `None` si el mes no existe. Para leer, no para asentar."""
    return PeriodoContableRepo(session).get_by_anio_mes(empresa_id, fecha.year, fecha.month)


def periodo_para_registrar(
    session: Session, empresa_id: uuid.UUID, fecha: date
) -> PeriodoContable | None:
    """El periodo donde escribir un asiento de esa fecha. **Lo abre si no
    existe**; `None` significa una sola cosa: el mes está cerrado.

    Antes esto era un lookup puro, y ahí estaba el agujero que dejó el balance
    en cero durante meses (ADR-089): `abrir_periodo` solo se llamaba desde el
    endpoint manual —no hay job, ni cron, ni seeder—, así que **un mes que
    nadie abrió descartaba en silencio todos los asientos automáticos del ERP
    entero**. Y no descartaba por una decisión de negocio: descartaba porque
    faltaba una fila que nadie sabía que había que crear.

    Abrirlo solo no debilita RN-CTB-010. La regla prohíbe asentar en un
    periodo **cerrado** —contra eso protege, y sigue protegiendo—; un mes que
    nunca se abrió no está cerrado, no existe. El control real del cierre es
    `cerrar_periodo`, que sigue siendo un acto explícito.

    ponytail: `abrir_periodo` hace get-y-si-no-add sin candado. Techo
    conocido: dos operaciones concurrentes en el **primer** asiento de un mes
    pueden chocar contra el UNIQUE de `(empresa, anio, mes)`; la que pierde
    reintenta y encuentra el periodo hecho. Si algún día eso pasa seguido, es
    un `INSERT ... ON CONFLICT DO NOTHING`, no un lock.
    """
    periodo = periodo_de_fecha(session, empresa_id, fecha)
    if periodo is None:
        periodo = abrir_periodo(
            session, empresa_id=empresa_id, anio=fecha.year, mes=fecha.month
        )
    return periodo if rules.puede_registrar(periodo.estado) else None
