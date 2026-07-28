"""lote: identidad trazable de un conjunto de unidades de un artículo.

Nace en la recepción de compra (vencimiento declarado por el proveedor,
RN-VNC-002) o en producción (vencimiento por normativa/laboratorio,
RN-VNC-001). El código lo asigna el ERP (RN-LOT-001).

Los campos de trazabilidad de fabricación (manipulador, envasador, línea,
variables de proceso, QR) se modelan en el slice de `production` — este
slice cubre lo que FEFO necesita: qué vence primero y de dónde vino.
"""

import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin

ORIGEN_LOTE = Enum(
    "compra",
    "produccion",
    "carga_inicial",
    "ajuste",
    name="origen_lote",
    native_enum=False,
)

CONDICION_ALMACENAMIENTO = Enum(
    "refrigerado",
    "congelado",
    "ambiente",
    name="condicion_almacenamiento",
    native_enum=False,
)


class Lote(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "lote"
    __table_args__ = (UniqueConstraint("articulo_id", "codigo"),)

    articulo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articulo.id"))
    codigo: Mapped[str] = mapped_column(String(50))
    # NULL = artículo con lote pero sin vencimiento declarado; FEFO lo
    # ordena al final y cae en FIFO por fecha de ingreso.
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_elaboracion: Mapped[date | None] = mapped_column(Date, nullable=True)
    origen: Mapped[str] = mapped_column(ORIGEN_LOTE)
    # Documento que lo originó (OC, orden de producción, carga inicial).
    referencia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    condicion_almacenamiento: Mapped[str | None] = mapped_column(
        CONDICION_ALMACENAMIENTO, nullable=True
    )
