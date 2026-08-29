"""Casos de uso de `asistencia`: marcar entrada/salida (RN-RRHH-009 — no
marcado no se considera; RN-PER-002 — locación de servicios no marca)."""

import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.rrhh.application.errors import NoEncontrado, ReglaNegocio
from src.modules.rrhh.infrastructure.models import Asistencia
from src.modules.rrhh.infrastructure.repositories import AsistenciaRepo, TrabajadorRepo


def _get_trabajador_habilitado(session: Session, trabajador_id: uuid.UUID):
    trabajador = TrabajadorRepo(session).get(trabajador_id)
    if trabajador is None:
        raise NoEncontrado(f"trabajador {trabajador_id} no encontrado")
    if not trabajador.registra_asistencia:
        raise ReglaNegocio(
            "trabajador no registra asistencia en el ERP (RN-PER-002)"
        )
    return trabajador


def marcar_entrada(
    session: Session, *, trabajador_id: uuid.UUID, fecha: date, hora_entrada: time,
    tardanza_min: int = 0, turno_id: uuid.UUID | None = None,
) -> Asistencia:
    _get_trabajador_habilitado(session, trabajador_id)
    repo = AsistenciaRepo(session)
    asistencia = repo.get_por_trabajador_fecha(trabajador_id, fecha)
    if asistencia is None:
        asistencia = repo.add(
            Asistencia(
                trabajador_id=trabajador_id,
                fecha=fecha,
                hora_entrada=hora_entrada,
                tardanza_min=tardanza_min,
                turno_id=turno_id,
            )
        )
    else:
        asistencia.hora_entrada = hora_entrada
        asistencia.tardanza_min = tardanza_min
        if turno_id is not None:
            asistencia.turno_id = turno_id
    return asistencia


def marcar_salida(
    session: Session, *, trabajador_id: uuid.UUID, fecha: date, hora_salida: time,
    horas_extra: Decimal = Decimal(0),
) -> Asistencia:
    """`horas_extra` llega en 0 salvo que RRHH la escriba a mano: quedarse
    de más no genera horas extra (RN-RRHH-022), y el pad nunca la manda."""
    _get_trabajador_habilitado(session, trabajador_id)
    repo = AsistenciaRepo(session)
    asistencia = repo.get_por_trabajador_fecha(trabajador_id, fecha)
    if asistencia is None:
        raise NoEncontrado("no hay marcación de entrada para esta fecha")
    asistencia.hora_salida = hora_salida
    asistencia.horas_extra = horas_extra
    return asistencia


def listar_asistencia_de_trabajador(
    session: Session, trabajador_id: uuid.UUID
) -> list[Asistencia]:
    return AsistenciaRepo(session).list_por_trabajador(trabajador_id)


def obtener(session: Session, asistencia_id: uuid.UUID) -> Asistencia | None:
    return AsistenciaRepo(session).get(asistencia_id)
