"""conteo: recuento físico de un almacén, opcionalmente acotado a una
categoría (RN-INV-014).

La periodicidad no es universal: la fija cada categoría
(`categoria.frecuencia_conteo`, RN-INV-007). Un conteo sin `categoria_id`
es un conteo general y satisface a todas las categorías de ese almacén.

Al cerrarse, cada diferencia genera un `ajuste` pendiente de aprobación —
el conteo nunca toca el stock por su cuenta.
"""

import datetime
import uuid

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin

TIPO_CONTEO = Enum(
    "rutina",
    "ajuste",
    "auditoria",
    name="tipo_conteo",
    native_enum=False,
)

ESTADO_CONTEO = Enum(
    "abierto",
    "cerrado",
    "anulado",
    name="estado_conteo",
    native_enum=False,
)


class Conteo(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "conteo"

    almacen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("almacen.id"))
    # NULL = conteo general (todas las categorías del almacén).
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categoria.id"), nullable=True
    )
    tipo: Mapped[str] = mapped_column(TIPO_CONTEO, default="rutina")
    estado: Mapped[str] = mapped_column(ESTADO_CONTEO, default="abierto")
    # Fecha en que el programa cíclico exigía este conteo. NULL en un conteo
    # ad-hoc (auditoría sorpresa o categoría sin frecuencia configurada).
    fecha_programada: Mapped[datetime.date | None] = mapped_column(
        Date, nullable=True
    )
    abierto_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    cerrado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    cerrado_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    observacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
