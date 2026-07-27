"""Lado hub del pull: upsert de las filas que mandó la nube.

Upsert por clave primaria, no por `INSERT ... ON CONFLICT`: la PK viaja
desde la nube (mismo UUID en ambos lados), así que insertar y actualizar
son el mismo caso y el código sirve igual en Postgres y en SQLite.

La nube es la única fuente de verdad de todo lo que se replica hacia
abajo: si el hub tocó una de esas filas, el valor de la nube gana.
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from src.core.sync import serializacion
from src.core.sync.contratos import RecursoSync

log = logging.getLogger("provecho.sync")


def importar(
    session: Session, recurso: RecursoSync, filas: list[dict]
) -> tuple[int, datetime | None]:
    """Devuelve (filas aplicadas, marca máxima vista)."""
    aplicadas = 0
    marca_max: datetime | None = None
    for datos in filas:
        clave = serializacion.clave_primaria(datos, recurso)
        fila = session.get(recurso.modelo, clave if len(clave) > 1 else clave[0])
        if fila is None:
            fila = recurso.modelo()
            session.add(fila)
        serializacion.aplicar_dict(fila, datos, recurso)
        aplicadas += 1
        marca = serializacion.marca_de(datos, recurso)
        if marca is not None and (marca_max is None or marca > marca_max):
            marca_max = marca
    if aplicadas:
        session.flush()
        log.debug("sync pull %s: %s filas", recurso.nombre, aplicadas)
    return aplicadas, marca_max
