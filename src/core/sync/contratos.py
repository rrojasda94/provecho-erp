"""Contrato de replicación hub↔nube (ADR-009, fase 2).

Un `RecursoSync` describe UNA entidad replicable hacia el hub: qué modelo,
qué campos viajan por el cable y cómo se acota al alcance de la sucursal.

Los módulos declaran los suyos en su `application/sincronizacion.py` —
`core/sync` solo sabe leer el descriptor, nunca conoce el dominio de
ningún módulo. Un módulo nuevo se vuelve replicable declarando su lista y
registrándola en `core/sync/registro.py`, sin tocar el motor.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import Select

# Direcciones del sync, tal como se guardan en `sync_watermark.direccion`.
PULL = "pull"
PUSH = "push"


@dataclass(frozen=True)
class AlcanceHub:
    """Tenant del hub: una sucursal de una empresa (ADR-009 — un hub por
    sucursal, nunca dos). Todo recurso se filtra contra esto."""

    empresa_id: uuid.UUID
    sucursal_id: uuid.UUID


Filtro = Callable[[Select, AlcanceHub], Select]


@dataclass(frozen=True)
class RecursoSync:
    """Una entidad replicada nube → hub.

    `campos` es el contrato de cable: solo esas columnas viajan, así que
    agregar una columna al modelo no la filtra sin querer hacia el hub.
    `campo_marca` es la columna de watermark incremental (`updated_at` en
    todo modelo con `TimestampMixin`; `ts` en los que no lo tienen).
    """

    nombre: str
    modelo: type
    campos: tuple[str, ...]
    filtro: Filtro
    campo_marca: str = "updated_at"
    # Solo documentación: por qué el hub necesita esta tabla durante un corte.
    motivo: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        columnas = set(self.modelo.__table__.c.keys())
        faltantes = sorted(set(self.campos) - columnas)
        if faltantes:
            raise ValueError(
                f"recurso {self.nombre}: campos inexistentes {faltantes}"
            )
        if self.campo_marca not in columnas:
            raise ValueError(
                f"recurso {self.nombre}: campo_marca '{self.campo_marca}' inexistente"
            )
        claves = {c.name for c in self.modelo.__table__.primary_key}
        if not claves <= set(self.campos):
            raise ValueError(
                f"recurso {self.nombre}: la PK {sorted(claves)} debe viajar en campos"
            )
