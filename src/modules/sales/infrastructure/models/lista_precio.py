"""Lista de precios: el precio lo fija el sistema, no el cliente (RN-PRC-003).

Ámbito opcional por sucursal / canal / modalidad de consumo (RN-MDC-003):
un campo en NULL significa "aplica a todas". Entre listas vigentes gana la
promocional; a igualdad, la más específica (data-model.md §3).

Cambiar un precio regular = nueva lista vigente, nunca editar la vigente
(RN-PRC-005, auditable igual que una OC).
"""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class ListaPrecio(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "lista_precio"

    marca_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("marca.id"))
    nombre: Mapped[str] = mapped_column(String(100))
    # Ámbito: NULL = sin restricción en esa dimensión.
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )
    canal: Mapped[str | None] = mapped_column(
        Enum("pdv", "agente_ia", "delivery", name="canal_lista_precio",
             native_enum=False),
        nullable=True,
    )
    modalidad: Mapped[str | None] = mapped_column(
        Enum("mesa", "takeout", "delivery", name="modalidad_lista_precio",
             native_enum=False),
        nullable=True,
    )
    # Una lista promocional gana sobre la regular mientras esté vigente; al
    # vencer, el precio regular se restaura solo (sin intervención manual).
    es_promocional: Mapped[bool] = mapped_column(Boolean, default=False)
    vigente_desde: Mapped[date] = mapped_column(Date)
    vigente_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
