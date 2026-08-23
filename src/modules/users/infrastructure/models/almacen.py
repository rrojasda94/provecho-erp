"""Almacén: contenedor de stock (central, producción, sucursal, activos)."""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import (
    SoftDeleteMixin,
    TimestampMixin,
    UbicacionMixin,
    UuidPkMixin,
)


class Almacen(
    Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin, UbicacionMixin
):
    __tablename__ = "almacen"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    # NULL si es central, de producción o virtual de activos.
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )
    nombre: Mapped[str] = mapped_column(String(100))
    # Enum extensible (ej. futuro `transporte` como hub físico, RN-TRP-003)
    # — String a propósito. `activos` es virtual, sin stock de SKUs.
    tipo: Mapped[str] = mapped_column(String(30))
    # NULL en los almacenes sin ubicación física (`activos`, `transporte`)
    # y en los de sucursal, cuya dirección es la de su sucursal.
    direccion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # El central del que se abastece un almacén de sucursal/producción.
    almacen_abastecedor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("almacen.id"), nullable=True
    )
    # A quién se le pide cuando el principal no está disponible. Vive acá y no
    # en `sucursal` porque el que se abastece es el almacén: una sucursal
    # puede tener más de uno (salón y cocina) y no todos se abastecen igual.
    # Poner el par en `sucursal` sería una segunda fuente de la misma verdad.
    almacen_abastecedor_respaldo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("almacen.id"), nullable=True
    )
