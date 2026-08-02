"""transferencia: stock que salió de un almacén y todavía no entró al otro.

Genérica por `origen_almacen_id`/`destino_almacen_id`: cubre igual
central→sucursal (surtiendo una solicitud) que la transferencia lateral
sucursal↔sucursal, que va sin solicitud detrás.

`en_transito` no es una ubicación física: es el estado del inventario ya
descontado del origen y aún no ingresado al destino (RN-INV-003).
"""

import datetime
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin

ESTADO_TRANSFERENCIA = Enum(
    "en_transito",
    "recibida",
    name="estado_transferencia",
    native_enum=False,
)


class Transferencia(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "transferencia"

    origen_almacen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("almacen.id"))
    destino_almacen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("almacen.id"))
    # NULL en la transferencia lateral: nadie la pidió, se acordó entre
    # locales (excepción documentada, no cambia el modelo).
    solicitud_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("solicitud_insumos.id"), nullable=True
    )
    estado: Mapped[str] = mapped_column(ESTADO_TRANSFERENCIA, default="en_transito")
    despachado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    recibido_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    # Quien la lleva. `vehiculo` no existe todavía como entidad — cuando
    # exista, entra acá su FK (ver ROADMAP → Deuda técnica).
    transportista_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    recibida_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    observacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
