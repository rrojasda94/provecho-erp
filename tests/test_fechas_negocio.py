"""La fecha del negocio no depende de dónde corra el proceso.

El ERP tiene tres relojes —la base en UTC, el proceso con la zona del
sistema (UTC dentro de Docker), y el negocio en America/Lima— y mezclarlos
corría el calendario un día: pasadas las 19:00 hora Perú, un conteo cerrado
"hoy" quedaba fechado mañana, y el programa de conteo cíclico se desfasaba.

Estos casos congelan la regla: `fechas.hoy()` responde por la zona
configurada del negocio, y todo timestamp de la base se traduce a esa zona
antes de convertirse en una fecha de calendario.
"""

import datetime
import os
from zoneinfo import ZoneInfo

import pytest

from src.config.settings import settings
from src.shared import fechas


@pytest.fixture()
def zona_lima(monkeypatch):
    monkeypatch.setattr(settings, "zona_horaria", "America/Lima")


def test_hoy_sale_de_la_zona_del_negocio_no_de_la_del_proceso(zona_lima):
    """Las 02:00 UTC del 4 de agosto son las 21:00 del 3 en Lima: para el
    negocio ese turno todavía es del 3, aunque el servidor diga otra cosa."""
    esperado = datetime.datetime.now(ZoneInfo("America/Lima")).date()
    assert fechas.hoy() == esperado

    # El mismo instante, leído desde otra zona, da otro día del negocio.
    monkey = ZoneInfo("Pacific/Kiritimati")  # UTC+14, el extremo opuesto
    settings.zona_horaria = "Pacific/Kiritimati"
    try:
        assert fechas.hoy() == datetime.datetime.now(monkey).date()
    finally:
        settings.zona_horaria = "America/Lima"


def test_un_timestamp_sin_zona_se_lee_como_utc(zona_lima):
    """Lo que escriben `func.now()` y los `server_default` viene sin zona
    —SQLite ni siquiera la guarda— y es UTC. Interpretarlo como hora local
    era justo el error: 02:00 del 4 en UTC es el 3 para el negocio."""
    guardado = datetime.datetime(2026, 8, 4, 2, 0, 0)  # naive, como la base
    assert fechas.a_fecha_local(guardado) == datetime.date(2026, 8, 3)

    # Antes del corte de las 19:00 hora Perú, el día coincide.
    assert fechas.a_fecha_local(datetime.datetime(2026, 8, 4, 15, 0)) == datetime.date(2026, 8, 4)


def test_un_timestamp_con_zona_se_convierte_no_se_ignora(zona_lima):
    """Postgres devuelve `timestamptz` con zona: hay que convertir, no
    quedarse con la parte de fecha del original."""
    con_zona = datetime.datetime(2026, 8, 4, 1, 30, tzinfo=datetime.UTC)
    assert fechas.a_fecha_local(con_zona) == datetime.date(2026, 8, 3)
    assert fechas.a_fecha_local(None) is None


# Las tres formas de leer el reloj del proceso en vez del del negocio. La
# primera es la que causó el desfase original; las otras dos se colaron
# después porque el barrido solo buscaba la primera.
PROHIBIDO = {
    "date.today": "la fecha local del proceso, en vez de `fechas.hoy()`",
    "datetime.now()": "la hora local del proceso, sin zona: `datetime.now(UTC)` "
    "para un instante, `fechas.ahora()` para una franja horaria",
    "datetime.utcnow": "un naive que miente sobre ser UTC (y está deprecado)",
}


def test_ningun_modulo_lee_el_reloj_del_proceso():
    """`date.today()` devuelve la zona del sistema: en Docker, UTC. Un módulo
    que la use vuelve a desfasar el calendario cinco horas, así que la regla
    se congela acá y no en una convención que nadie relee.

    Se busca `date.today` **sin** los paréntesis a propósito: como `default`
    de una columna la función viaja sin llamar (`default=date.today`), que es
    la misma bomba con otra sintaxis y pasaba el barrido anterior."""
    raiz = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
    culpables = []
    for carpeta, _, archivos in os.walk(raiz):
        if "__pycache__" in carpeta:
            continue
        for archivo in archivos:
            if not archivo.endswith(".py"):
                continue
            ruta = os.path.join(carpeta, archivo)
            # `fechas.py` las nombra en su docstring para explicar por qué no
            # se usan.
            if ruta.endswith("fechas.py"):
                continue
            texto = open(ruta, encoding="utf-8").read()
            for patron, motivo in PROHIBIDO.items():
                if patron in texto:
                    culpables.append(f"{os.path.relpath(ruta, raiz)}: `{patron}` es {motivo}")
    assert not culpables, "leen el reloj del proceso:\n" + "\n".join(culpables)
