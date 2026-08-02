"""Divisa: catálogo de monedas y **cuántos decimales** usa cada una.

Entidad transversal (vive en `shared`, mismo criterio que `Comprobante`): el
dinero no es de ningún módulo. Existe porque los decimales no son 2 por
decreto — hay monedas de 0 y de 3 — y porque toda magnitud monetaria debe
poder nombrar su unidad (RN-GER-010, `magnitudes.py`).

Hoy la operación es PEN única (RN-PRC-004) y `precio` sigue sin columna de
divisa; esta tabla no cambia eso.
"""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Divisa(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "divisa"

    codigo: Mapped[str] = mapped_column(String(3), unique=True)  # ISO 4217: PEN, USD
    nombre: Mapped[str] = mapped_column(String(50))
    simbolo: Mapped[str] = mapped_column(String(5))  # S/, $
    decimales: Mapped[int] = mapped_column(Integer, default=2)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
