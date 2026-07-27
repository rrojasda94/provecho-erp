"""ReglaAprobacion: matriz de aprobaciones como tabla — entidad transversal,
mismo criterio que `Comprobante` (sirve a varios módulos, vive en `shared`).

Reemplaza el umbral fijo en config para reglas cuantitativas (RN-GER-003:
fuente única, ninguna área fija su propio umbral). `docs/gerencia/
politica-gerencia.md#matriz-de-aprobaciones` sigue siendo la fuente
narrativa/de gobierno para lo no tabular.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class ReglaAprobacion(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "regla_aprobacion"
    __table_args__ = (UniqueConstraint("empresa_id", "modulo", "codigo"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    modulo: Mapped[str] = mapped_column(String(50))  # ej. "purchases"
    codigo: Mapped[str] = mapped_column(String(50))  # ej. "oc_umbral"
    umbral: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Informativo — la verificación real del permiso la hace el módulo consumidor.
    permiso_requerido: Mapped[str] = mapped_column(String(100))
    vigente: Mapped[bool] = mapped_column(Boolean, default=True)
