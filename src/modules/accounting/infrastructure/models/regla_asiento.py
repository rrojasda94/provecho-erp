"""Mapeo configurable evento operativo → cuentas de contrapartida. Sin una
regla vigente para `empresa_id`+`evento`, el asiento automático se omite
(se loguea, nunca bloquea el proceso de origen) — mismo criterio que
`regla_aprobacion` para umbrales (RN-GER-003): la empresa configura, el
código no hardcodea su propio plan de cuentas."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class ReglaAsiento(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "regla_asiento"
    __table_args__ = (UniqueConstraint("empresa_id", "evento"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    evento: Mapped[str] = mapped_column(String(100))  # ej. "purchases.oc_emitida"
    cuenta_debe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuenta_contable.id"))
    cuenta_haber_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuenta_contable.id"))
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
