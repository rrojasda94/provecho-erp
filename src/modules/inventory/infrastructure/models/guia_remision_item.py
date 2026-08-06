"""guia_remision_item: qué bienes declara la guía y en qué cantidad.

Las líneas **se derivan** de `transferencia_item`, nunca se teclean:
RN-TRP-002 exige que lo transportado coincida exactamente con lo declarado,
y un formulario aparte es justamente la forma de que no coincidan.

Se agrupan **por SKU**, no por lote. El despacho reparte por FEFO y una
línea de 10 kg puede salir de tres lotes (ADR-015), pero eso es control
interno: SUNAT declara producto y cantidad. La trazabilidad por lote sigue
completa en `transferencia_item`, que es donde importa.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class GuiaRemisionItem(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "guia_remision_item"

    guia_remision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guia_remision.id")
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sku.id"))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    # Snapshot: el nombre del artículo puede cambiar y la guía ya emitida
    # tiene que seguir describiendo lo que viajó ese día.
    descripcion: Mapped[str] = mapped_column(String(255))
    # Código de unidad de SUNAT (catálogo 03). Snapshot por el mismo motivo.
    unidad: Mapped[str] = mapped_column(String(5), default="NIU")
