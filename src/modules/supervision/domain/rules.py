"""Reglas puras de supervisión: cuándo toca una tarea, si el checklist está
completo, si la foto es de ahora y quién puede ejecutar la tarea.

Sin ORM, sin FastAPI, sin `src.core`/`src.shared`/`src.modules` — dominio
puro (`tests/test_arquitectura.py` lo exige).
"""

import uuid
from datetime import UTC, date, datetime, timedelta

FRECUENCIAS = ("diaria", "interdiaria", "semanal", "mensual")
MOMENTOS = ("apertura", "cierre")
ESTADOS_TAREA = ("pendiente", "completada", "vencida")


def toca_hoy(
    *,
    frecuencia: str,
    fecha_inicio: date,
    hoy: date,
    dia_semana: int | None = None,
    dia_mes: int | None = None,
) -> bool:
    """Si la plantilla genera una instancia para `hoy`.

    Nunca antes de `fecha_inicio`: una plantilla creada hoy no fabrica
    tareas retroactivas para ayer.
    """
    if hoy < fecha_inicio:
        return False
    if frecuencia == "diaria":
        return True
    if frecuencia == "interdiaria":
        return (hoy - fecha_inicio).days % 2 == 0
    if frecuencia == "semanal":
        return dia_semana is not None and hoy.weekday() == dia_semana
    if frecuencia == "mensual":
        return dia_mes is not None and hoy.day == dia_mes
    raise ValueError(f"frecuencia desconocida: {frecuencia}")


def _como_instante_utc(momento: datetime) -> datetime:
    """SQLite no guarda zona: un `DateTime(timezone=True)` vuelve naive tras
    el viaje de ida y vuelta, con los mismos dígitos con que se escribió
    (mismo criterio que `src/shared/fechas.py::a_fecha_local`: naive == UTC,
    porque así es como `application/fotos.py` guarda `foto_tomada_at`)."""
    return momento if momento.tzinfo is not None else momento.replace(tzinfo=UTC)


def foto_es_de_ahora(
    tomada_at: datetime | None, ahora: datetime, tolerancia_minutos: int
) -> bool | None:
    """`True`/`False` si hay fecha EXIF que comparar, `None` si no la hay
    (foto sin metadato o cámara sin GPS/reloj configurado — no es prueba de
    fraude, es una foto que no se puede validar)."""
    if tomada_at is None:
        return None
    diferencia = _como_instante_utc(ahora) - _como_instante_utc(tomada_at)
    return abs(diferencia.total_seconds()) <= tolerancia_minutos * 60


def checklist_completo(items: list[dict]) -> bool:
    return bool(items) and all(item.get("hecho") for item in items)


def puede_ejecutar(asignado_a: uuid.UUID | None, actor_id: uuid.UUID) -> bool:
    """Sin asignar = nadie la puede ejecutar todavía (RN-SUP-003): hay que
    asignarla primero. Evita que cualquiera se adjudique una tarea huérfana."""
    return asignado_a is not None and asignado_a == actor_id


def puede_completar(
    *, checklist: list[dict], requiere_foto: bool, tiene_foto: bool
) -> bool:
    if not checklist_completo(checklist):
        return False
    if requiere_foto and not tiene_foto:
        return False
    return True


def vencida_al_cierre(estado: str) -> bool:
    """Una tarea que sigue `pendiente` cuando se genera el informe del día
    se considera vencida (RN-SUP-007): no hay ventana de gracia, la jornada
    ya cerró."""
    return estado == "pendiente"


def foto_expirada(completada_at: datetime, ahora: datetime, retencion_dias: int) -> bool:
    return completada_at < ahora - timedelta(days=retencion_dias)
