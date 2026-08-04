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
    return datetime.datetime.now(zona()).date()


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
