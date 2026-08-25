"""Barrido de salidas sin marcar (RN-RRHH-021).

Quien entró y no marcó su salida pasada la hora límite de su turno recibe
un recordatorio, y con él el encargado del local y RRHH. El aviso **no
cierra la jornada**: la marcación sigue faltando hasta que alguien la
ponga, y quedarse de más nunca se convierte en horas extra (RN-RRHH-022).

Dos destinos por dos caminos distintos, y no es una duplicación:

- **El trabajador** recibe una notificación en su propia campana. Es a
  quien va dirigido el pedido, y no tiene —ni va a tener— `rrhh.leer`, que
  es lo que el motor de reportes exige para abrir un reporte (RN-REP-002).
- **El encargado y RRHH** reciben el reporte `rrhh.salida_sin_marcar`, que
  es lo que se administra desde la matriz de distribución.

Idempotente por `asistencia.reporte_salida_en`: el barrido puede correr
cada hora sin repetirle el aviso a nadie.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.rrhh.application.pad_asistencia import LIMA, fecha_laboral
from src.modules.rrhh.infrastructure.models import Asistencia, Trabajador
from src.modules.rrhh.infrastructure.repositories import (
    AsistenciaRepo,
    TurnoSucursalRepo,
)
from src.modules.users.application.queries_publicas import notificar_a
from src.modules.users.infrastructure.models import Persona

TIPO_AVISO = "rrhh.salida_sin_marcar"


def _limite(asistencia: Asistencia, turno) -> datetime:
    """El momento exacto en que vencía la marcación de salida.

    Cuando la hora límite es menor que la de inicio, el turno cruza la
    medianoche y el vencimiento cae al día siguiente: el turno noche que
    entra 22:00 y tiene límite 03:00 vence de madrugada, no doce horas
    antes de haber empezado.
    """
    dia = asistencia.fecha
    if turno.hora_limite_salida < turno.hora_inicio:
        dia = dia + timedelta(days=1)
    return datetime.combine(dia, turno.hora_limite_salida, tzinfo=LIMA)


def _nombre(session: Session, trabajador: Trabajador) -> str:
    persona = session.get(Persona, trabajador.persona_id)
    if persona is None:
        return "(sin nombre)"
    return f"{persona.nombres} {persona.apellidos}".strip()


def _fechas_a_revisar(momento: datetime) -> list[date]:
    """El día laboral en curso y el anterior.

    Dos y no uno porque el turno noche vence de madrugada, cuando el día
    laboral ya cambió: mirar solo el día en curso dejaría esa salida sin
    avisar hasta nunca.
    """
    hoy = fecha_laboral(momento)
    return [hoy - timedelta(days=1), hoy]


def barrer(session: Session, momento: datetime | None = None) -> list[uuid.UUID]:
    """Avisa por cada marcación vencida y devuelve los ids de asistencia.

    Una marcación sin turno no se avisa: sin turno no hay hora límite
    contra la cual estar vencido. Una sin centro de labores tampoco, porque
    el reporte es de ámbito sucursal y no tendría a qué local atribuirse
    — las dos son configuración faltante, no una falta del trabajador.
    """
    momento = momento or datetime.now(LIMA)
    repo = AsistenciaRepo(session)
    turnos_repo = TurnoSucursalRepo(session)
    avisadas: list[uuid.UUID] = []

    for fecha in _fechas_a_revisar(momento):
        for asistencia, trabajador in repo.sin_salida(fecha):
            if asistencia.turno_id is None or trabajador.sucursal_id is None:
                continue
            turno = turnos_repo.get(asistencia.turno_id)
            if turno is None or momento <= _limite(asistencia, turno):
                continue

            nombre = _nombre(session, trabajador)
            hora_entrada = asistencia.hora_entrada.strftime("%H:%M")
            hora_limite = turno.hora_limite_salida.strftime("%H:%M")

            if trabajador.usuario_id is not None:
                notificar_a(
                    session,
                    trabajador.usuario_id,
                    tipo=TIPO_AVISO,
                    titulo="Te falta marcar tu salida",
                    cuerpo=(
                        f"Entraste {hora_entrada} del {asistencia.fecha} y no "
                        f"marcaste salida antes de {hora_limite}. Márcala en el "
                        "pad del local o avísale a tu encargado."
                    ),
                    sucursal_id=trabajador.sucursal_id,
                )

            event_bus.publish(
                TIPO_AVISO,
                {
                    "trabajador_id": str(trabajador.id),
                    "sucursal_id": str(trabajador.sucursal_id),
                    "trabajador": nombre,
                    "fecha": str(asistencia.fecha),
                    "turno": turno.nombre,
                    "hora_entrada": hora_entrada,
                    "hora_limite": hora_limite,
                },
                session=session,
            )
            asistencia.reporte_salida_en = datetime.now(UTC)
            avisadas.append(asistencia.id)

    return avisadas
