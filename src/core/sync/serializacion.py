"""Conversión fila ↔ JSON para el sync (ADR-009, fase 2).

Genérica a propósito: los tipos se leen de la columna SQLAlchemy, no de
una tabla de mapeo por entidad. Así un recurso nuevo no necesita código de
serialización propio.

Todo viaja como texto (UUID, Decimal, fecha/hora): JSON no tiene esos
tipos y un `float` para un monto es exactamente el error que Numeric evita.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Column

from src.core.sync.contratos import RecursoSync


def _a_json(valor: Any) -> Any:
    if isinstance(valor, uuid.UUID | Decimal):
        return str(valor)
    if isinstance(valor, datetime | date):
        return valor.isoformat()
    return valor


def _tipo_python(columna: Column) -> type | None:
    try:
        return columna.type.python_type
    except NotImplementedError:  # JSON/JSONB: viaja tal cual
        return None


def _desde_json(valor: Any, columna: Column) -> Any:
    if valor is None:
        return None
    tipo = _tipo_python(columna)
    if tipo is None or isinstance(valor, tipo):
        return valor
    if tipo is uuid.UUID:
        return uuid.UUID(str(valor))
    if tipo is Decimal:
        return Decimal(str(valor))
    if tipo is datetime:
        return datetime.fromisoformat(valor)
    if tipo is date:
        return date.fromisoformat(valor)
    return tipo(valor)


def a_dict(fila: object, recurso: RecursoSync) -> dict:
    return {campo: _a_json(getattr(fila, campo)) for campo in recurso.campos}


def aplicar_dict(destino: object, datos: dict, recurso: RecursoSync) -> None:
    """Escribe en `destino` los campos del recurso presentes en `datos`.

    `updated_at` se copia con el valor de la nube (no el reloj del hub):
    el watermark de pull compara siempre contra el mismo reloj. SQLAlchemy
    respeta el valor explícito y no dispara el `onupdate` de la columna.
    """
    columnas = recurso.modelo.__table__.c
    for campo in recurso.campos:
        if campo in datos:
            setattr(destino, campo, _desde_json(datos[campo], columnas[campo]))


def clave_primaria(datos: dict, recurso: RecursoSync) -> tuple:
    columnas = recurso.modelo.__table__.primary_key
    return tuple(_desde_json(datos[c.name], c) for c in columnas)


def marca_de(datos: dict, recurso: RecursoSync) -> datetime | None:
    valor = datos.get(recurso.campo_marca)
    return None if valor is None else datetime.fromisoformat(valor)
