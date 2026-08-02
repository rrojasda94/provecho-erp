"""ajuste: corrección de stock con segregación de funciones.

Solicitar y aprobar son permisos distintos (`inventory.solicitar_ajuste` /
`inventory.aprobar_ajuste`) y nunca el mismo usuario (RN-INV-015). Al
aprobarse genera el `movimiento_inventario` tipo `ajuste`.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin
from src.modules.inventory.infrastructure.models.movimiento_inventario import (
    MOTIVO_AJUSTE,
)

ESTADO_AJUSTE = Enum(
    "pendiente",
    "aprobado",
    "rechazado",
    name="estado_ajuste",
    native_enum=False,
)


class Ajuste(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "ajuste"

    almacen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("almacen.id"))
    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sku.id"))
    # Delta con signo: + sobrante, − faltante/merma.
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    motivo: Mapped[str] = mapped_column(MOTIVO_AJUSTE)
    # Conteo que lo originó, si vino de uno (RN-INV-014). NULL = ajuste
    # solicitado a mano.
    conteo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conteo.id"), nullable=True
    )
    solicitado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    aprobado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    # Fuera del margen de error (acordado con accounting) exige investigación
    # y dispara inventory.ajuste_fuera_margen (RN-INV-015).
    dentro_margen: Mapped[bool] = mapped_column(Boolean, default=True)
    estado: Mapped[str] = mapped_column(ESTADO_AJUSTE, default="pendiente")
    movimiento_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("movimiento_inventario.id"), nullable=True
    )
