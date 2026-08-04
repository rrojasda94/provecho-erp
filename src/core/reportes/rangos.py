"""Rangos de fecha de un reporte: presets del negocio + rango libre.

Todos se derivan de `fechas.hoy()` (zona del negocio), nunca de la fecha
local del proceso: "este mes" tiene que significar lo mismo para el gerente
que mira a las 21:00 hora Perú que para el proceso que corre en UTC.

El preset viaja como código, no como par de fechas ya resuelto, porque un
tablero guardado con "mes actual" tiene que seguir diciendo *el mes actual*
la próxima vez que se abra — no el mes en que se guardó.
"""

import datetime
from collections.abc import Callable

from src.shared import fechas

Rango = tuple[datetime.date, datetime.date]


def _dia(hoy: datetime.date, offset: int = 0) -> Rango:
    d = hoy - datetime.timedelta(days=offset)
    return d, d


def _ultimos(hoy: datetime.date, dias: int) -> Rango:
    # Incluye hoy: "últimos 7 días" son hoy y los 6 anteriores.
    return hoy - datetime.timedelta(days=dias - 1), hoy


def _semana_actual(hoy: datetime.date) -> Rango:
    return hoy - datetime.timedelta(days=hoy.weekday()), hoy


def _mes_actual(hoy: datetime.date) -> Rango:
    return hoy.replace(day=1), hoy


def _mes_pasado(hoy: datetime.date) -> Rango:
    fin = hoy.replace(day=1) - datetime.timedelta(days=1)
    return fin.replace(day=1), fin


def _anio_actual(hoy: datetime.date) -> Rango:
    return hoy.replace(month=1, day=1), hoy


PRESETS: dict[str, Callable[[datetime.date], Rango]] = {
    "hoy": lambda h: _dia(h),
    "ayer": lambda h: _dia(h, 1),
    "ultimos_7": lambda h: _ultimos(h, 7),
    "ultimos_30": lambda h: _ultimos(h, 30),
    "ultimos_90": lambda h: _ultimos(h, 90),
    "semana_actual": _semana_actual,
    "mes_actual": _mes_actual,
    "mes_pasado": _mes_pasado,
    "anio_actual": _anio_actual,
}

# Etiquetas para que el frontend no repita el catálogo ni lo traduzca solo.
ETIQUETAS = {
    "hoy": "Hoy",
    "ayer": "Ayer",
    "ultimos_7": "Últimos 7 días",
    "ultimos_30": "Últimos 30 días",
    "ultimos_90": "Últimos 90 días",
    "semana_actual": "Semana actual",
    "mes_actual": "Mes actual",
    "mes_pasado": "Mes pasado",
    "anio_actual": "Año actual",
    "personalizado": "Personalizado",
}

PERSONALIZADO = "personalizado"

# Tope duro del rango consultable. No es una preferencia de UI: sin esto,
# `desde=1900-01-01` es un escaneo de tabla completa que cualquier usuario
# autenticado puede pedir en bucle.
MAX_DIAS = 731  # dos años


class RangoInvalido(Exception):
    """El rango pedido no se puede resolver (→ HTTP 422)."""


def resolver(
    preset: str,
    desde: datetime.date | None = None,
    hasta: datetime.date | None = None,
) -> Rango:
    """Convierte preset (o rango libre) en un par de fechas concreto."""
    if preset != PERSONALIZADO:
        calcular = PRESETS.get(preset)
        if calcular is None:
            raise RangoInvalido(f"Rango '{preset}' no existe")
        return calcular(fechas.hoy())

    if desde is None or hasta is None:
        raise RangoInvalido("Un rango personalizado necesita 'desde' y 'hasta'")
    if desde > hasta:
        raise RangoInvalido("'desde' no puede ser posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise RangoInvalido(f"El rango no puede superar {MAX_DIAS} días")
    return desde, hasta
