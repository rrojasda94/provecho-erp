"""Casos de uso del turno de trabajo: alta, edición, listado y —lo único
con lógica de verdad— resolver qué turno le toca a una marcación.

`turno_vigente` no pregunta: el trabajador toca su tarjeta y el servidor
decide. Pedirle el turno sería pedirle que se autoevalúe la tardanza.
"""

import uuid
from datetime import datetime, time

from sqlalchemy.orm import Session

from src.modules.rrhh.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.rrhh.infrastructure.models import TurnoSucursal
from src.modules.rrhh.infrastructure.repositories import TurnoSucursalRepo
from src.modules.users.infrastructure.models import Sucursal

EDITABLES = (
    "nombre",
    "hora_inicio",
    "hora_fin",
    "tolerancia_min",
    "hora_limite_salida",
    "activo",
)


def crear_turno(
    session: Session,
    *,
    sucursal_id: uuid.UUID,
    nombre: str,
    hora_inicio: time,
    hora_fin: time,
    hora_limite_salida: time,
    tolerancia_min: int = 5,
) -> TurnoSucursal:
    sucursal = session.get(Sucursal, sucursal_id)
    if sucursal is None or sucursal.deleted_at is not None:
        raise NoEncontrado(f"sucursal {sucursal_id} no encontrada")
    repo = TurnoSucursalRepo(session)
    if repo.por_nombre(sucursal_id, nombre) is not None:
        raise Conflicto(f"la sucursal ya tiene un turno '{nombre}'")
    _validar_tolerancia(tolerancia_min)
    return repo.add(
        TurnoSucursal(
            empresa_id=sucursal.empresa_id,
            sucursal_id=sucursal_id,
            nombre=nombre,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            hora_limite_salida=hora_limite_salida,
            tolerancia_min=tolerancia_min,
        )
    )


def editar_turno(session: Session, turno_id: uuid.UUID, **campos) -> TurnoSucursal:
    repo = TurnoSucursalRepo(session)
    turno = repo.get(turno_id)
    if turno is None:
        raise NoEncontrado("turno no encontrado")
    nombre = campos.get("nombre")
    if nombre is not None and nombre != turno.nombre:
        if repo.por_nombre(turno.sucursal_id, nombre) is not None:
            raise Conflicto(f"la sucursal ya tiene un turno '{nombre}'")
    if campos.get("tolerancia_min") is not None:
        _validar_tolerancia(campos["tolerancia_min"])
    for campo in EDITABLES:
        if campos.get(campo) is not None:
            setattr(turno, campo, campos[campo])
    return turno


def listar_turnos(
    session: Session, sucursal_id: uuid.UUID, solo_activos: bool = False
) -> list[TurnoSucursal]:
    return TurnoSucursalRepo(session).list_de_sucursal(sucursal_id, solo_activos)


def _validar_tolerancia(minutos: int) -> None:
    # Una tolerancia negativa adelantaría la hora de entrada, y una de medio
    # día haría que no exista la tardanza.
    if not 0 <= minutos <= 120:
        raise ReglaNegocio("la tolerancia debe estar entre 0 y 120 minutos")


def _minutos(momento: time) -> int:
    return momento.hour * 60 + momento.minute


def _dentro(turno: TurnoSucursal, minuto: int) -> bool:
    """¿El minuto del día cae dentro de la ventana del turno?

    La ventana abre con la tolerancia ya descontada —quien llega puntual
    llega antes de su hora— y un turno que cruza medianoche se parte en dos
    tramos en vez de compararse al revés.
    """
    inicio = (_minutos(turno.hora_inicio) - turno.tolerancia_min) % (24 * 60)
    fin = _minutos(turno.hora_fin)
    if inicio <= fin:
        return inicio <= minuto <= fin
    return minuto >= inicio or minuto <= fin


def turno_vigente(
    session: Session, sucursal_id: uuid.UUID, momento: datetime
) -> TurnoSucursal | None:
    """El turno activo de la sucursal al que pertenece este momento.

    Si dos ventanas se pisan (el cambio de turno siempre se pisa un poco),
    gana el que empieza más cerca: quien marca a las 15:05 entra al turno de
    las 15:00, no al que empezó a las 07:00 y todavía no terminó.

    `None` cuando la sucursal no tiene turnos configurados o el momento cae
    fuera de todos: se marca igual, sin tardanza. Que no haya turno no puede
    impedirle a nadie fichar.
    """
    minuto = _minutos(momento.time())
    candidatos = [
        turno
        for turno in TurnoSucursalRepo(session).list_de_sucursal(
            sucursal_id, solo_activos=True
        )
        if _dentro(turno, minuto)
    ]
    if not candidatos:
        return None
    return min(candidatos, key=lambda t: (minuto - _minutos(t.hora_inicio)) % (24 * 60))


def tardanza_de(turno: TurnoSucursal | None, momento: datetime) -> int:
    """Minutos de tardanza sobre la hora de entrada, ya descontada la
    tolerancia. Sin turno no hay contra qué medir, así que es 0."""
    if turno is None:
        return 0
    atraso = (_minutos(momento.time()) - _minutos(turno.hora_inicio)) % (24 * 60)
    # Más de medio día de «atraso» es en realidad haber llegado antes.
    if atraso > 12 * 60:
        return 0
    return max(0, atraso - turno.tolerancia_min)
