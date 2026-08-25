"""Turno de trabajo de una sucursal: horario laboral, no turno de caja.

Dos cosas distintas se llamaban «turno» en el ERP y una sola estaba
modelada. El **turno de caja** (`accounting`) es la sesión de una caja
abierta, y de ahí sale el encargado de turno. El **turno de trabajo** es
esto: la franja en la que se espera que la gente del local esté, y contra
la que se mide si llegó tarde y hasta cuándo tiene que marcar su salida.

No vive en `parametro_empresa` (ADR-014) porque ese índice es
`(empresa_id, modulo, codigo)`: meter la sucursal dentro del `codigo`
perdería la FK, que es el mismo motivo por el que
`categoria.frecuencia_conteo` terminó siendo una columna.
"""

import uuid
from datetime import time

from sqlalchemy import Boolean, ForeignKey, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class TurnoSucursal(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "turno_sucursal"
    __table_args__ = (UniqueConstraint("sucursal_id", "nombre"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    nombre: Mapped[str] = mapped_column(String(50))
    hora_inicio: Mapped[time] = mapped_column(Time())
    # `hora_fin` menor que `hora_inicio` significa que el turno cruza la
    # medianoche — el turno noche de un restaurante es la norma, no el borde.
    hora_fin: Mapped[time] = mapped_column(Time())
    # Los minutos de gracia antes de contar tardanza. Es una perilla, no una
    # constante: cada local negocia su propio margen con su gente.
    tolerancia_min: Mapped[int] = mapped_column(default=5)
    # Pasada esta hora sin marcación de salida se avisa (RN-RRHH-021). No
    # cierra la asistencia ni genera horas extra: solo pide que la marquen.
    hora_limite_salida: Mapped[time] = mapped_column(Time())
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
