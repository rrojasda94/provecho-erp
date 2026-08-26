"""Semáforo del KDS: cuánto puede esperar un pedido antes de preocupar.

Hasta ahora la pantalla de cocina no tenía **ninguna** noción de tiempo. Los
colores de las tarjetas eran el estado (`en_preparacion` ámbar, `listo`
verde), que dice en qué anda el pedido pero no si lleva cuatro minutos o
cuarenta. Un pedido olvidado se veía exactamente igual que uno recién
tomado.

Los umbrales y los colores los fija **Gerencia** por empresa, con el mismo
mecanismo que la tarifa del delivery (ADR-014 Addendum, ADR-068): los
códigos viven acá —en el módulo dueño del parámetro— y se leen con
`parametros.valor_vigente`, que solo devuelve lo aprobado. Sin nada aprobado
manda la semilla de este archivo.

Por qué se configura y no se fija: ocho minutos son una eternidad para una
barra de bebidas y nada para un horno de pizza a leña. El número correcto lo
sabe quien mira la cocina, no quien escribe el código.

**Cuánto lleva no se calcula acá.** El backend manda `creado_en` en la cola y
el reloj lo hace el navegador: un cronómetro servidor obligaría a recalcular
y reenviar la cola entera cada segundo, cuando la pantalla ya sabe qué hora
es. Lo que el servidor sí define es a partir de qué minuto se pone ámbar.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from src.shared import parametros

MODULO = "sales"
CODIGO_MINUTOS_AMBAR = "kds_minutos_ambar"
CODIGO_MINUTOS_ROJO = "kds_minutos_rojo"
CODIGO_COLOR_NORMAL = "kds_color_normal"
CODIGO_COLOR_AMBAR = "kds_color_ambar"
CODIGO_COLOR_ROJO = "kds_color_rojo"

CODIGOS = (
    CODIGO_MINUTOS_AMBAR,
    CODIGO_MINUTOS_ROJO,
    CODIGO_COLOR_NORMAL,
    CODIGO_COLOR_AMBAR,
    CODIGO_COLOR_ROJO,
)

# La semilla son los colores que ya tenía `kds.css` y unos minutos de
# arranque razonables para una pizzería: el primero es "mirá esto", el
# segundo "andá a ver qué pasó".
SEMILLA_MINUTOS_AMBAR = 8
SEMILLA_MINUTOS_ROJO = 15
SEMILLA_COLOR_NORMAL = "#22c55e"
SEMILLA_COLOR_AMBAR = "#fbbf24"
SEMILLA_COLOR_ROJO = "#f87171"

# Un umbral de más de cuatro horas no es un umbral, es un parámetro tecleado
# mal; uno de cero pinta todo de rojo desde el primer segundo y apaga el
# semáforo entero sin decirlo.
MINUTOS_MINIMO = 1
MINUTOS_MAXIMO = 240


@dataclass(frozen=True)
class Semaforo:
    """Los cinco valores con los que la pantalla pinta una tarjeta.

    Se resuelve entero y se pasa entero, igual que `Tarifa`: leer parámetro
    por parámetro dentro de cada uso sería una consulta por número y dejaría
    que dos partes de la misma pantalla usaran configuraciones distintas si
    alguien aprueba un cambio en el medio.
    """

    minutos_ambar: int
    minutos_rojo: int
    color_normal: str
    color_ambar: str
    color_rojo: str


def semilla() -> Semaforo:
    return Semaforo(
        minutos_ambar=SEMILLA_MINUTOS_AMBAR,
        minutos_rojo=SEMILLA_MINUTOS_ROJO,
        color_normal=SEMILLA_COLOR_NORMAL,
        color_ambar=SEMILLA_COLOR_AMBAR,
        color_rojo=SEMILLA_COLOR_ROJO,
    )


def color_valido(valor: Any) -> bool:
    """`#rrggbb`, seis dígitos hexadecimales. Se valida el **formato** y no el
    contraste: un color ilegible es una decisión de quien lo eligió y se
    arregla mirando la pantalla, pero un valor que no es un color rompe el
    CSS de toda la cocina."""
    if not isinstance(valor, str) or len(valor) != 7 or not valor.startswith("#"):
        return False
    return all(c in "0123456789abcdefABCDEF" for c in valor[1:])


def _color(valor: Any, defecto: str) -> str:
    """Tolerante igual que la tarifa: el valor pasó por un formulario y por
    una pantalla de aprobación, y uno mal formado tiene que dejar el color de
    fábrica, no dejar la cocina sin pantalla."""
    if isinstance(valor, dict) and color_valido(valor.get("color")):
        return str(valor["color"])
    return defecto


def _minutos(valor: Any, defecto: int) -> int:
    if not isinstance(valor, dict):
        return defecto
    try:
        minutos = int(valor["minutos"])
    except (KeyError, TypeError, ValueError):
        return defecto
    if not MINUTOS_MINIMO <= minutos <= MINUTOS_MAXIMO:
        return defecto
    return minutos


def semaforo_de(session: Session, empresa_id: uuid.UUID | None) -> Semaforo:
    """El semáforo vigente de la empresa, con la semilla de respaldo.

    Si el rojo quedara antes o igual que el ámbar el semáforo no tendría tres
    niveles sino dos, y el ámbar sería invisible: en ese caso manda la
    semilla completa, que sí es coherente. Corregir uno de los dos números
    contra el otro dejaría una combinación que nadie aprobó.
    """
    base = semilla()
    if empresa_id is None:
        return base

    def vigente(codigo: str) -> Any:
        return parametros.valor_vigente(session, empresa_id, MODULO, codigo)

    ambar = _minutos(vigente(CODIGO_MINUTOS_AMBAR), base.minutos_ambar)
    rojo = _minutos(vigente(CODIGO_MINUTOS_ROJO), base.minutos_rojo)
    if rojo <= ambar:
        ambar, rojo = base.minutos_ambar, base.minutos_rojo
    return Semaforo(
        minutos_ambar=ambar,
        minutos_rojo=rojo,
        color_normal=_color(vigente(CODIGO_COLOR_NORMAL), base.color_normal),
        color_ambar=_color(vigente(CODIGO_COLOR_AMBAR), base.color_ambar),
        color_rojo=_color(vigente(CODIGO_COLOR_ROJO), base.color_rojo),
    )
