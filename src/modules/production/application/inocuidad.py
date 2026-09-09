"""Checklist de inocuidad de turno (RN-CDP-002/005): bioseguridad,
superficies, limpieza intermedia, equipos de frío y posible indicio de
plaga. `crear_checklist` calcula `estado` — nunca lo decide quien lo
registra — y `exigir_cocina_habilitada` es el gate que `application/
ordenes.py` llama antes de crear una orden o registrar consumo: sin un
checklist `aprobado` vigente en el almacén, la cocina está bloqueada.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.production.application.errors import CocinaBloqueada, Conflicto, NoEncontrado
from src.modules.production.domain import rules
from src.modules.production.infrastructure.models import ChecklistInocuidadTurno
from src.modules.production.infrastructure.repositories import ChecklistInocuidadTurnoRepo
from src.modules.users.infrastructure.models import Almacen
from src.shared import auditoria, fechas


def q_checklists(
    session: Session,
    *,
    empresa_id: uuid.UUID | None = None,
    almacen_id: uuid.UUID | None = None,
    fecha: date | None = None,
    estado: str | None = None,
):
    """La consulta sin ejecutar, para que el router la pagine (ADR-026)."""
    return ChecklistInocuidadTurnoRepo(session).q_list(
        empresa_id=empresa_id, almacen_id=almacen_id, fecha=fecha, estado=estado
    )


def crear_checklist(
    session: Session,
    *,
    almacen_id: uuid.UUID,
    fecha: date,
    turno: str,
    verificado_por: uuid.UUID,
    bioseguridad_ok: bool,
    superficies_ok: bool,
    limpieza_intermedia_ok: bool,
    # [{equipo, temperatura_c, rango_min, rango_max}] — sin `dentro_rango`:
    # lo calcula este caso de uso, nunca lo manda el cliente.
    equipos_frio: list[dict],
    plaga_indicio: bool,
    ip: str | None = None,
) -> ChecklistInocuidadTurno:
    almacen = session.get(Almacen, almacen_id)
    if almacen is None:
        raise NoEncontrado(f"almacén {almacen_id} no encontrado")
    repo = ChecklistInocuidadTurnoRepo(session)
    if repo.get_por_clave(almacen_id, fecha, turno) is not None:
        raise Conflicto(
            f"ya existe un checklist para el turno '{turno}' de {fecha} en ese almacén"
        )

    equipos_calculados = []
    equipos_dentro_rango = []
    for eq in equipos_frio:
        temperatura_c = Decimal(str(eq["temperatura_c"]))
        rango_min = Decimal(str(eq["rango_min"]))
        rango_max = Decimal(str(eq["rango_max"]))
        dentro_rango = rules.equipo_dentro_rango(temperatura_c, rango_min, rango_max)
        equipos_dentro_rango.append(dentro_rango)
        equipos_calculados.append(
            {
                "equipo": eq["equipo"],
                "temperatura_c": str(temperatura_c),
                "rango_min": str(rango_min),
                "rango_max": str(rango_max),
                "dentro_rango": dentro_rango,
            }
        )

    aprobado = rules.checklist_aprobado(
        bioseguridad_ok=bioseguridad_ok,
        superficies_ok=superficies_ok,
        limpieza_intermedia_ok=limpieza_intermedia_ok,
        equipos_dentro_rango=equipos_dentro_rango,
        plaga_indicio=plaga_indicio,
    )
    estado = "aprobado" if aprobado else "bloqueado"

    checklist = repo.add(
        ChecklistInocuidadTurno(
            almacen_id=almacen_id,
            fecha=fecha,
            turno=turno,
            verificado_por=verificado_por,
            bioseguridad_ok=bioseguridad_ok,
            superficies_ok=superficies_ok,
            limpieza_intermedia_ok=limpieza_intermedia_ok,
            equipos_frio=equipos_calculados,
            plaga_indicio=plaga_indicio,
            estado=estado,
        )
    )
    auditoria.registrar(
        session,
        usuario_id=verificado_por,
        entidad="checklist_inocuidad_turno",
        accion="crear",
        entidad_id=checklist.id,
        datos_despues={
            "estado": estado,
            "almacen_id": str(almacen_id),
            "fecha": fecha.isoformat(),
            "turno": turno,
        },
        empresa_id=almacen.empresa_id,
        ip=ip,
    )

    for eq in equipos_calculados:
        if not eq["dentro_rango"]:
            event_bus.publish(
                "production.equipo_frio_fuera_rango",
                {
                    "checklist_id": str(checklist.id),
                    "almacen_id": str(almacen_id),
                    "equipo": eq["equipo"],
                    "temperatura_c": eq["temperatura_c"],
                    "rango_min": eq["rango_min"],
                    "rango_max": eq["rango_max"],
                },
                session=session,
            )
    if estado == "bloqueado":
        motivo = "indicio de plaga" if plaga_indicio else "equipo de frío fuera de rango"
        event_bus.publish(
            "production.cocina_bloqueada",
            {
                "checklist_id": str(checklist.id),
                "almacen_id": str(almacen_id),
                "turno": turno,
                "fecha": fecha.isoformat(),
                "motivo": motivo,
            },
            session=session,
        )
    return checklist


def exigir_cocina_habilitada(
    session: Session, almacen_id: uuid.UUID, *, fecha: date | None = None
) -> None:
    """Gate de RN-CDP-005 para crear orden y registrar consumo: sin
    checklist `aprobado` vigente del día en el almacén, la cocina está
    bloqueada (409 `CocinaBloqueada`)."""
    fecha = fecha or fechas.hoy()
    checklist = ChecklistInocuidadTurnoRepo(session).vigente_de(almacen_id, fecha)
    if checklist is None or checklist.estado != "aprobado":
        raise CocinaBloqueada(
            "cocina_bloqueada: no hay checklist de inocuidad aprobado del turno "
            "vigente en este almacén (RN-CDP-005)"
        )
