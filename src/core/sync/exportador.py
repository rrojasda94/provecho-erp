"""Lado nube del pull: lee filas de un recurso acotadas al hub que pregunta.

Genérico sobre `RecursoSync` — no hay una función por entidad. El filtro de
tenant lo pone el módulo dueño del recurso; acá solo se aplica.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.sync import serializacion
from src.core.sync.contratos import AlcanceHub, RecursoSync
from src.core.sync.tiempo import para_dialecto


def exportar(
    session: Session,
    recurso: RecursoSync,
    alcance: AlcanceHub,
    desde: datetime | None,
    limite: int,
) -> list[dict]:
    """Filas del recurso con `campo_marca >= desde`, más antiguas primero.

    `>=` y no `>`: con `>` una fila escrita en el mismo microsegundo que la
    marca guardada se perdería para siempre. Reprocesar la fila del borde
    en cada ciclo es un upsert idempotente — barato al lado de perder una.

    ponytail: el costo es que todas las filas que comparten exactamente la
    marca del watermark vuelven a viajar cada ciclo, y `now()` en Postgres
    es el reloj de la transacción: un catálogo sembrado de una sola vez y
    nunca tocado se baja entero en cada ciclo. Con el tamaño de un catálogo
    de restaurante son unos cientos de KB por minuto y no vale la pena
    resolverlo todavía. Si el enlace del local lo empieza a sentir, la
    salida es paginación por cursor compuesto `(marca, pk)` en vez de solo
    `marca` — ver ROADMAP → Deuda técnica → Modo offline.
    """
    marca = getattr(recurso.modelo, recurso.campo_marca)
    consulta = recurso.filtro(select(recurso.modelo), alcance)
    if desde is not None:
        consulta = consulta.where(marca >= para_dialecto(session, desde))
    consulta = consulta.order_by(marca).limit(limite)
    return [
        serializacion.a_dict(fila, recurso) for fila in session.scalars(consulta)
    ]
