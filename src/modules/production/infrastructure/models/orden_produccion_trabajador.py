"""Trabajador imputado a una orden y sus horas (RN-PRD-018).

Reemplaza el `horas_hombre` tipeado a mano: las horas de cada trabajador
salen de su asistencia real del día (`rrhh.application.queries_publicas.
horas_asistidas`), no de un número libre que nadie podía contrastar contra
nada. `orden_produccion.horas_hombre` sigue existiendo como el agregado
(`Σ horas`), para no romper el costeo que ya lo multiplica por la tarifa.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import UuidPkMixin


class OrdenProduccionTrabajador(Base, UuidPkMixin):
    __tablename__ = "orden_produccion_trabajador"

    orden_produccion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orden_produccion.id"))
    trabajador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trabajador.id"))
    horas: Mapped[Decimal] = mapped_column(Numeric(8, 2))
