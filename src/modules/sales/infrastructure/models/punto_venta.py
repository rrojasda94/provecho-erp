"""Punto de venta: lugar virtual asociado a una sucursal (trabajador,
web o kiosko).
"""

import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class PuntoVenta(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "punto_venta"

    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    canal: Mapped[str] = mapped_column(
        Enum("trabajador", "web", "kiosko", name="canal_punto_venta", native_enum=False)
    )
    # NULL si canal=web.
    hardware_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Series SUNAT separadas (decisión 2026-07-20) — comprobante.serie
    # copia el valor vigente al emitir (snapshot inmutable).
    serie_boleta: Mapped[str] = mapped_column(String(10))
    serie_factura: Mapped[str] = mapped_column(String(10))
    # Array `mesa`|`takeout`|`delivery` (RN-MDC-001).
    modalidades_habilitadas: Mapped[list | None] = mapped_column(JsonB, nullable=True)
    # Ej. delivery exige dirección (RN-MDC-002).
    datos_minimos_por_modalidad: Mapped[dict | None] = mapped_column(
        JsonB, nullable=True
    )
    politica_pago: Mapped[str] = mapped_column(
        Enum(
            "adelantado",
            "al_finalizar",
            name="politica_pago_punto_venta",
            native_enum=False,
        )
    )
    kpis: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
