"""Registro de la evidencia de cada marcación (RN-RRHH-024, ADR-073).

`asistencia` es la fila-resumen del día; esto es la fila por toque, con lo
que RRHH mira cuando algo no cuadra: quién firmó, desde qué terminal (NULL
= corrección de back-office), con qué IP, a qué distancia del local y con
qué foto.

La distancia se calcula acá y no se guarda como bandera de "anomalía": el
reporte la deriva comparando contra `sucursal.radio_marcaje_m` en el
momento de leer, así que corregir el radio de un local reclasifica su
histórico solo, en vez de dejarlo congelado con un criterio viejo.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.orm import Session

from src.modules.rrhh.infrastructure.models import Asistencia, Marcacion, TerminalMarcaje
from src.modules.rrhh.infrastructure.repositories import AsistenciaRepo, MarcacionRepo
from src.modules.users.infrastructure.models import Sucursal
from src.shared.ubicacion import metros_entre


def _distancia_m(
    sucursal: Sucursal | None, lat: Decimal | None, lng: Decimal | None
) -> int | None:
    if sucursal is None or sucursal.ubicacion_lat is None or lat is None or lng is None:
        return None
    return metros_entre(sucursal.ubicacion_lat, sucursal.ubicacion_lng, lat, lng)


def registrar(
    session: Session,
    *,
    asistencia: Asistencia,
    tipo: str,
    usuario_id: uuid.UUID,
    momento: datetime,
    terminal: TerminalMarcaje | None = None,
    ip: str | None = None,
    lat: Decimal | None = None,
    lng: Decimal | None = None,
    sucursal_id: uuid.UUID | None = None,
    foto: bytes | None = None,
) -> Marcacion:
    sucursal = session.get(Sucursal, sucursal_id) if sucursal_id is not None else None
    marcacion = MarcacionRepo(session).add(
        Marcacion(
            asistencia_id=asistencia.id,
            tipo=tipo,
            momento=momento,
            usuario_id=usuario_id,
            terminal_id=terminal.id if terminal is not None else None,
            ip=ip,
            ubicacion_lat=lat,
            ubicacion_lng=lng,
            distancia_m=_distancia_m(sucursal, lat, lng),
            foto=foto,
        )
    )
    if terminal is not None:
        terminal.ultima_marcacion_en = momento
    return marcacion


def listar_de_asistencia(session: Session, asistencia_id: uuid.UUID) -> list[Marcacion]:
    return MarcacionRepo(session).list_de_asistencia(asistencia_id)


def obtener(session: Session, marcacion_id: uuid.UUID) -> Marcacion | None:
    return MarcacionRepo(session).get(marcacion_id)


def trabajador_id_de(session: Session, marcacion: Marcacion) -> uuid.UUID | None:
    """De qué trabajador es esta marcación, vía su `asistencia` — para que
    el router pueda validar el alcance de tenant sin tocar el modelo."""
    asistencia = AsistenciaRepo(session).get(marcacion.asistencia_id)
    return None if asistencia is None else asistencia.trabajador_id


def purgar_fotos_vencidas(session: Session, dias: int) -> int:
    """Borra el binario de las fotos más viejas que `dias`; la fila y el
    resto de la evidencia (terminal, IP, distancia) se quedan (RN-RRHH-024).

    `UPDATE` a granel y no fila por fila: es una purga, no una auditoría —
    no hay nada que decidir marcación por marcación.
    """
    limite = datetime.now(UTC) - timedelta(days=dias)
    resultado = session.execute(
        update(Marcacion)
        .where(Marcacion.momento < limite, Marcacion.foto.isnot(None))
        .values(foto=None)
    )
    return resultado.rowcount or 0
