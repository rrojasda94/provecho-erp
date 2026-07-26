"""Casos de uso de `solicitud_permiso`: crear → aprobar/rechazar
(RN-RRHH-005)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.rrhh.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.rrhh.domain import rules
from src.modules.rrhh.infrastructure.models import SolicitudPermiso
from src.modules.rrhh.infrastructure.repositories import SolicitudPermisoRepo, TrabajadorRepo


def crear_solicitud_permiso(
    session: Session,
    *,
    trabajador_id: uuid.UUID,
    tipo: str,
    fecha_desde: date,
    fecha_hasta: date | None = None,
    horas: Decimal | None = None,
    motivo: str | None = None,
) -> SolicitudPermiso:
    if tipo not in rules.TIPOS_SOLICITUD_PERMISO:
        raise ReglaNegocio(f"tipo de solicitud inválido: {tipo}")
    if tipo == "permiso_horas" and horas is None:
        raise ReglaNegocio("tipo 'permiso_horas' requiere horas")
    if tipo != "permiso_horas" and fecha_hasta is None:
        raise ReglaNegocio(f"tipo '{tipo}' requiere fecha_hasta")
    if TrabajadorRepo(session).get(trabajador_id) is None:
        raise NoEncontrado(f"trabajador {trabajador_id} no encontrado")

    return SolicitudPermisoRepo(session).add(
        SolicitudPermiso(
            trabajador_id=trabajador_id,
            tipo=tipo,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            horas=horas,
            motivo=motivo,
        )
    )


def listar_solicitudes_de_trabajador(
    session: Session, trabajador_id: uuid.UUID
) -> list[SolicitudPermiso]:
    return SolicitudPermisoRepo(session).list_por_trabajador(trabajador_id)


def _resolver(
    session: Session, solicitud_id: uuid.UUID, *, aprobador_id: uuid.UUID, nuevo_estado: str
) -> SolicitudPermiso:
    solicitud = SolicitudPermisoRepo(session).get(solicitud_id)
    if solicitud is None:
        raise NoEncontrado("solicitud no encontrada")
    if not rules.puede_resolver_solicitud_permiso(solicitud.estado):
        raise Conflicto(f"solicitud está {solicitud.estado}; no admite resolución")
    solicitud.estado = nuevo_estado
    solicitud.aprobador_id = aprobador_id
    if nuevo_estado == "aprobada":
        event_bus.publish(
            "rrhh.solicitud_permiso_aprobada",
            {
                "solicitud_permiso_id": str(solicitud.id),
                "trabajador_id": str(solicitud.trabajador_id),
                "tipo": solicitud.tipo,
            },
        )
    return solicitud


def aprobar_solicitud_permiso(
    session: Session, solicitud_id: uuid.UUID, *, aprobador_id: uuid.UUID
) -> SolicitudPermiso:
    return _resolver(session, solicitud_id, aprobador_id=aprobador_id, nuevo_estado="aprobada")


def rechazar_solicitud_permiso(
    session: Session, solicitud_id: uuid.UUID, *, aprobador_id: uuid.UUID
) -> SolicitudPermiso:
    return _resolver(session, solicitud_id, aprobador_id=aprobador_id, nuevo_estado="rechazada")
