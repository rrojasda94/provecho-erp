"""Catálogo de recursos replicables, en orden de dependencia.

`core/sync` ensambla las declaraciones de cada módulo igual que
`core/app.py` ensambla sus routers: el motor no conoce ninguna entidad de
negocio, solo esta lista. Un módulo que quiera replicar algo declara su
tupla `RECURSOS` y la agrega acá.

**El orden importa**: es el orden de importación en el hub y las FK se
respetan de arriba hacia abajo (organización → catálogo de inventario →
catálogo comercial). Al revés, la primera fila hija fallaría por falta de
padre.
"""

from src.core.sync.contratos import RecursoSync
from src.modules.inventory.application import sincronizacion as inventory_push
from src.modules.inventory.application.sincronizacion import (
    RECURSOS as RECURSOS_INVENTORY,
)
from src.modules.sales.application import sincronizacion as sales_push
from src.modules.sales.application.sincronizacion import RECURSOS as RECURSOS_SALES
from src.modules.users.application.sincronizacion import RECURSOS as RECURSOS_USERS

RECURSOS: tuple[RecursoSync, ...] = (
    *RECURSOS_USERS,
    *RECURSOS_INVENTORY,
    *RECURSOS_SALES,
)

# Módulos que **empujan** (hub → nube). Cada uno expone `RECURSO_PUSH`
# (nombre de su watermark), `pendientes(session, alcance, desde, limite)` y
# `aplicar(session, lote, alcance) -> (resumen, a_encolar)`.
#
# El orden importa por la misma razón que en `RECURSOS`, pero al revés de lo
# que parece: `sales` va primero porque la venta descuenta stock, y el
# conteo que `inventory` reproduce después tiene que medir contra un stock
# que ya incluye lo vendido durante el corte. Al revés, la nube generaría
# ajustes por mercadería que sí se había vendido.
MODULOS_PUSH = (sales_push, inventory_push)

POR_NOMBRE = {recurso.nombre: recurso for recurso in RECURSOS}

if len(POR_NOMBRE) != len(RECURSOS):
    raise RuntimeError("hay recursos de sync con nombre repetido")


def obtener(nombre: str) -> RecursoSync | None:
    return POR_NOMBRE.get(nombre)
