"""La fecha del **negocio**: ni la del servidor ni la de la base.

Un ERP tiene tres relojes y confundirlos corre el calendario un día:

- La base escribe sus `created_at`/`cerrado_at` en **UTC** (`func.now()`,
  `CURRENT_TIMESTAMP`). Correcto: un instante no se guarda con zona local.
- El proceso corre con la zona del sistema, que en Docker es **UTC** y en la
  laptop de quien desarrolla es la de su país. `date.today()` devuelve una u
  otra según dónde corra, que es exactamente lo que no se quiere.
- El negocio abre y cierra en **America/Lima**. Un conteo cerrado el lunes a
  las 20:00 es del lunes para el almacenero, aunque en UTC ya sea martes.

Cuando un dato es un **instante** (cuándo pasó), va en UTC y no se toca.
Cuando es una **fecha de calendario** (de qué día es esto para el negocio),
se deriva con estas funciones. Mezclar las dos cosas fue la causa de que el
calendario de conteos se corriera un día pasadas las 19:00 hora Perú.
"""

import datetime
from zoneinfo import ZoneInfo

from src.config.settings import settings


def zona() -> ZoneInfo:
    return ZoneInfo(settings.zona_horaria)


def hoy() -> datetime.date:
    """Qué día es **para el negocio**, sin importar dónde corra el proceso."""
    return ahora().date()


def ahora() -> datetime.datetime:
    """El instante, en hora del negocio.

    Lo usa lo que decide por franja horaria —una promoción de happy hour, un
    turno— donde la fecha sola no alcanza. `datetime.now()` a secas daría la
    hora del contenedor, que en Docker es UTC: un martes de pizzas hasta las
    23:00 se apagaría a las 18:00 hora Perú.
    """
    return datetime.datetime.now(zona())


def desfase_horas(referencia: datetime.date | None = None) -> int:
    """Horas que hay que sumarle a un instante UTC para leerlo en hora local.

    Perú no aplica horario de verano desde 1994, así que el desfase es
    constante (-5) y se puede usar para **reetiquetar** un agrupamiento que
    la base hizo en UTC en vez de convertir fila por fila: agrupar por hora
    en SQL da 24 filas, y correr la etiqueta de cada una es exacto mientras
    el desfase sea de horas enteras.

    Se deriva de la zona configurada y no se escribe `-5` a mano: si algún
    día el negocio abre en otro país, esto sigue estando bien. `referencia`
    existe para poder pedir el desfase de una fecha concreta si esa zona sí
    tuviera horario de verano.
    """
    momento = datetime.datetime.combine(referencia or hoy(), datetime.time(12))
    desfase = momento.replace(tzinfo=zona()).utcoffset()
    assert desfase is not None
    segundos = int(desfase.total_seconds())
    if segundos % 3600:
        raise ValueError(
            f"La zona {settings.zona_horaria} tiene un desfase que no es de "
            "horas enteras: reetiquetar buckets horarios daría mal."
        )
    return segundos // 3600


def inicio_dia_utc(dia: datetime.date) -> datetime.datetime:
    """Instante UTC en que **empieza** ese día de calendario del negocio.

    Para filtrar por rango una columna que la base guarda en UTC
    (`created_at`) usando fechas que el usuario piensa en hora Perú: comparar
    `created_at >= date(...)` crudo corre el borde hasta 5 horas.
    """
    local = datetime.datetime.combine(dia, datetime.time.min, tzinfo=zona())
    return local.astimezone(datetime.UTC)


def fin_dia_utc(dia: datetime.date) -> datetime.datetime:
    """Instante UTC en que **termina** ese día de calendario del negocio."""
    local = datetime.datetime.combine(dia, datetime.time.max, tzinfo=zona())
    return local.astimezone(datetime.UTC)


def a_fecha_local(momento: datetime.datetime | None) -> datetime.date | None:
    """Fecha de calendario del negocio para un instante guardado en la base.

    Un timestamp sin zona se interpreta como UTC: es lo que escriben
    `func.now()` y los `server_default`, y también lo que devuelve SQLite,
    que no guarda zona en absoluto.
    """
    if momento is None:
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=datetime.UTC)
    return momento.astimezone(zona()).date()
