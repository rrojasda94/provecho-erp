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
    tardanza_min: int = 0,
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
            )
        )
    else:
        asistencia.hora_entrada = hora_entrada
        asistencia.tardanza_min = tardanza_min
    return asistencia


def marcar_salida(
    session: Session, *, trabajador_id: uuid.UUID, fecha: date, hora_salida: time,
    horas_extra: Decimal = Decimal(0),
) -> Asistencia:
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
