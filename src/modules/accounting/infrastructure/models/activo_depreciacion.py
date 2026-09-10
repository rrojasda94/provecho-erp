"""activo_depreciacion: cuánto lleva depreciado cada activo de `assets`.

`accounting` no tiene el activo —`valor_compra`/`vida_util_meses` viven en
`assets.Activo`—, así que esta fila es la única memoria del lado contable:
sin ella, el barrido mensual no sabría si un activo ya se depreció del todo
ni desde cuándo contarle la vida útil. La idempotencia del asiento en sí la
da `asiento.referencia_origen` (`<activo_id>:<AAAA-MM>`, único por evento);
esta tabla es la que permite calcular la cuota del mes siguiente sin
recorrer todo el historial de asientos.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class ActivoDepreciacion(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "activo_depreciacion"

    __table_args__ = (UniqueConstraint("activo_id", name="uq_activo_depreciacion_activo_id"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    # Sin FK: `activo` es dominio de `assets`.
    activo_id: Mapped[uuid.UUID] = mapped_column()
    # Congelados al primer barrido que ve el activo — si `assets` corrige el
    # valor de compra después, el ajuste es un asiento manual, no una
    # reescritura silenciosa de lo ya depreciado.
    valor_compra: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    vida_util_meses: Mapped[int] = mapped_column()
    fecha_inicio: Mapped[date] = mapped_column(Date)
    depreciado_acumulado: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal(0))
