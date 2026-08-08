"""Reglas puras de la distribución de reportes.

Sin ORM, sin FastAPI, sin red: se prueban sin levantar nada
(`tests/test_arquitectura.py` lo exige para todo `domain/`).
"""

from collections.abc import Sequence
from typing import Any, Protocol

TIPOS_DESTINATARIO = ("area", "rol", "usuario", "dinamico")

# Qué canal transporta la entrega. Hoy solo la bandeja in-app existe; el
# campo está para que agregar correo o WhatsApp no sea una migración de
# datos, sino una fila más (`notificacion.py`: "bandeja, no transporte").
CANALES = ("bandeja",)


class TieneSucursal(Protocol):
    sucursal_id: Any


def elegir_regla[T: TieneSucursal](
    reglas: Sequence[T], sucursal_id: Any | None
) -> T | None:
    """Cuál de las reglas de una emisión aplica a este hecho (RN-REP-008).

    La específica de la sucursal le gana a la general de la empresa. Si
    aplicaran las dos, un mismo hecho entregaría dos veces al que esté en
    ambas — y la que el administrador escribió para *este* local es la que
    quiso que mandara.

    Sin regla específica, la general (`sucursal_id` nulo) cubre. Sin ninguna
    de las dos, `None`: el hecho se registra igual y sale como hueco en la
    matriz (RN-REP-005).
    """
    general = None
    for regla in reglas:
        if sucursal_id is not None and regla.sucursal_id == sucursal_id:
            return regla
        if regla.sucursal_id is None:
            general = regla
    return general


def motivo(tipo: str, valor: str) -> str:
    """Por qué esta persona recibió este reporte.

    Se guarda en `entrega_reporte` y es la mitad del valor del hub: sin él,
    la matriz dice quién recibe pero no por qué, y nadie sabe qué tocar para
    cambiarlo. `rol:supervisor` se arregla en el rol; `area:almacen`, en el
    área.
    """
    return f"{tipo}:{valor}" if valor else tipo
