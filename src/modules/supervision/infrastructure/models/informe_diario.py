"""Informe diario de supervisión: el resumen de una sucursal al cerrar la
jornada. Es la entidad a la que apunta el reporte que entra al módulo
`reports` (ADR-033) — de ahí el supervisor lo escala con el mecanismo ya
existente (ADR-036), no con uno propio de este módulo."""

import uuid
from datetime import date, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class InformeDiario(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "informe_diario"

    __table_args__ = (UniqueConstraint("sucursal_id", "fecha"),)

    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    fecha: Mapped[date] = mapped_column()
    total: Mapped[int] = mapped_column(Integer, default=0)
    completadas: Mapped[int] = mapped_column(Integer, default=0)
    vencidas: Mapped[int] = mapped_column(Integer, default=0)
    fotos_invalidas: Mapped[int] = mapped_column(Integer, default=0)
    generado_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
