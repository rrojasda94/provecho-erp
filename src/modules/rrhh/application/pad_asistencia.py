"""El pad de marcación del local: tarjetas con nombre y PIN propio.

La tablet del comedor está logueada con la cuenta de servicio de la
sucursal (`terminal_asistencia`), que por sí sola no puede marcar nada:
solo listar los nombres de quienes marcan ahí y presentar una marcación
firmada. La firma es el PIN del trabajador, verificado contra el mismo
lockout del login (ADR-065, RN-RRHH-020).

Tres cosas las decide el servidor y no el cliente, y las tres por el mismo
motivo —el cliente es una tablet compartida en un mostrador—:

1. **La hora.** Viene del reloj del servidor en hora Perú. El reloj de una
   tablet lo cambia cualquiera desde ajustes.
2. **Si es entrada o salida.** Sale del estado del día, no de qué botón se
   tocó: si ya hay entrada sin salida, esto es la salida.
3. **La tardanza.** Se mide contra el turno vigente (`turnos.turno_vigente`).

Y una cuarta que no decide nadie: `horas_extra` es siempre 0. Quedarse de
más no es una hora extra (RN-RRHH-022); si corresponde pagarla, la
registra RRHH a mano.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.rrhh.application import asistencia as casos_asistencia
from src.modules.rrhh.application import turnos
from src.modules.rrhh.application.errors import Conflicto, NoEncontrado
from src.modules.rrhh.infrastructure.models import Asistencia, Trabajador
from src.modules.rrhh.infrastructure.repositories import AsistenciaRepo, TrabajadorRepo
from src.modules.users.application.queries_publicas import obtener_usuario
from src.modules.users.infrastructure.models import Persona

# El día laboral es el del local, no el del servidor: un turno noche que
# termina a las 02:00 tiene que caer en el día que empezó (ver `fecha_laboral`).
LIMA = ZoneInfo("America/Lima")

# Antes de esta hora, la marcación pertenece al día anterior. Cubre la
# salida del turno noche sin necesidad de preguntarle a nadie de qué día
# está marcando.
CORTE_DIA_LABORAL = 5


@dataclass(frozen=True)
class Tarjeta:
    """Lo único que el pad muestra de una persona: su nombre y si ya marcó.

    Nada de cargo, documento ni remuneración — la pantalla está a la vista
    de todo el que pase por la cocina.
    """

    trabajador_id: uuid.UUID
    nombre: str
    marco_entrada: bool
    marco_salida: bool


def ahora() -> datetime:
    return datetime.now(LIMA)


def fecha_laboral(momento: datetime) -> date:
    dia = momento.date()
    if momento.hour < CORTE_DIA_LABORAL:
        return date.fromordinal(dia.toordinal() - 1)
    return dia


def tarjetas(session: Session, sucursal_id: uuid.UUID) -> list[Tarjeta]:
    """Quiénes marcan hoy en este local, en una sola consulta."""
    fecha = fecha_laboral(ahora())
    filas = session.execute(
        select(Trabajador.id, Persona.nombres, Persona.apellidos)
        .join(Persona, Persona.id == Trabajador.persona_id)
        .where(
            Trabajador.sucursal_id == sucursal_id,
            Trabajador.estado == "activo",
            Trabajador.registra_asistencia.is_(True),
            Trabajador.deleted_at.is_(None),
        )
        .order_by(Persona.apellidos, Persona.nombres)
    ).all()
    if not filas:
        return []

    ids = [fila[0] for fila in filas]
    marcadas = {
        a.trabajador_id: a
        for a in session.scalars(
            select(Asistencia).where(
                Asistencia.trabajador_id.in_(ids), Asistencia.fecha == fecha
            )
        )
    }
    return [
        Tarjeta(
            trabajador_id=trabajador_id,
            nombre=f"{nombres} {apellidos}".strip(),
            marco_entrada=marcadas.get(trabajador_id) is not None
            and marcadas[trabajador_id].hora_entrada is not None,
            marco_salida=marcadas.get(trabajador_id) is not None
            and marcadas[trabajador_id].hora_salida is not None,
        )
        for trabajador_id, nombres, apellidos in filas
    ]


def usuario_que_firma(session: Session, trabajador_id: uuid.UUID) -> uuid.UUID:
    """El usuario cuyo PIN vale como firma de este trabajador.

    La cuenta se resuelve por persona (ADR-070): es la del `usuario` cuya
    `persona_id` es la de este trabajador. Sin cuenta no hay PIN, y sin PIN
    no hay firma: el trabajador marca en el back-office con
    `rrhh.asistencia_marcar` hasta que se le vincule una desde Usuarios. Se
    resuelve antes de pedir el PIN para que el error diga qué falta en vez
    de «credenciales inválidas».

    Una cuenta desactivada se rechaza acá y no en `verificar_pin_de`: sin
    esto caía a `PIN_INVALIDO` → 401 «credenciales inválidas», el mismo
    error engañoso que este método existe para evitar.
    """
    trabajador = TrabajadorRepo(session).get(trabajador_id)
    if trabajador is None or trabajador.deleted_at is not None:
        raise NoEncontrado(f"trabajador {trabajador_id} no encontrado")
    if trabajador.usuario_id is None:
        raise Conflicto(
            "esta persona no tiene cuenta con PIN: vinculala en Usuarios "
            "para que pueda marcar en el pad"
        )
    usuario = obtener_usuario(session, trabajador.usuario_id)
    if usuario is not None and not usuario.activo:
        raise Conflicto("la cuenta de este trabajador está desactivada")
    return trabajador.usuario_id


def sucursal_de(session: Session, trabajador_id: uuid.UUID) -> uuid.UUID | None:
    """El centro de labores del trabajador (ADR-062). El router lo compara
    con la sucursal del terminal: el pad de un local no marca por la gente
    de otro."""
    trabajador = TrabajadorRepo(session).get(trabajador_id)
    return None if trabajador is None else trabajador.sucursal_id


def marcar(
    session: Session, *, trabajador_id: uuid.UUID, momento: datetime | None = None
) -> tuple[Asistencia, str]:
    """Registra la marcación que toque y devuelve `(asistencia, tipo)`.

    `tipo` es `"entrada"` o `"salida"`. Volver a tocar la tarjeta después
    de haber marcado la salida es un conflicto explícito: sin eso, el
    segundo toque pisaría la hora de salida con la del momento y la jornada
    se estiraría sola.
    """
    momento = momento or ahora()
    fecha = fecha_laboral(momento)
    hora = momento.time().replace(microsecond=0)

    existente = AsistenciaRepo(session).get_por_trabajador_fecha(trabajador_id, fecha)
    if existente is not None and existente.hora_salida is not None:
        raise Conflicto("la jornada de hoy ya está cerrada: entrada y salida marcadas")

    if existente is not None and existente.hora_entrada is not None:
        asistencia = casos_asistencia.marcar_salida(
            session, trabajador_id=trabajador_id, fecha=fecha, hora_salida=hora
        )
        return asistencia, "salida"

    sucursal_id = sucursal_de(session, trabajador_id)
    turno = (
        turnos.turno_vigente(session, sucursal_id, momento)
        if sucursal_id is not None
        else None
    )
    asistencia = casos_asistencia.marcar_entrada(
        session,
        trabajador_id=trabajador_id,
        fecha=fecha,
        hora_entrada=hora,
        tardanza_min=turnos.tardanza_de(turno, momento),
        turno_id=turno.id if turno is not None else None,
    )
    return asistencia, "entrada"
