"""Proveedor: RUC + razón social (jurídico) o `persona_id` (natural, ej.
RHE) — mismo party model que `cliente` (RN-GEN-007), nunca duplica datos
de persona natural.

`formal`/`clasificacion` habilitan el camino simplificado de OC (RN-CMP-004)
y el flujo de compra menor a proveedor informal (RN-CMP-011..016, aún sin
modelar — deuda técnica, ver ROADMAP).
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import (
    SoftDeleteMixin,
    TimestampMixin,
    UbicacionMixin,
    UuidPkMixin,
)


class Proveedor(
    Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin, UbicacionMixin
):
    __tablename__ = "proveedor"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    tipo: Mapped[str] = mapped_column(
        Enum("natural", "juridico", name="tipo_proveedor", native_enum=False)
    )
    # Si tipo=natural — nombre/documento se leen de persona (RN-GEN-007).
    persona_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("persona.id"), nullable=True
    )
    # Si tipo=juridico.
    razon_social: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ruc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    contacto: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Domicilio fiscal, tal como lo devuelve SUNAT al consultar el RUC. Se
    # guarda partido y no como un solo texto porque `provincia` es lo que
    # decide si el flete es local o interprovincial, y volver a partir una
    # dirección concatenada es adivinar. `pais` existe para el proveedor
    # extranjero, que no tiene RUC ni provincia peruana.
    direccion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provincia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pais: Mapped[str] = mapped_column(String(60), default="PE")
    # `false` = proveedor informal de mercado/supermercado (RN-CMP-011).
    formal: Mapped[bool] = mapped_column(Boolean, default=True)
    clasificacion: Mapped[str] = mapped_column(
        Enum("regular", "preferente", name="clasificacion_proveedor", native_enum=False),
        default="regular",
    )
    condicion_pago: Mapped[str] = mapped_column(
        Enum("contado", "credito", name="condicion_pago_proveedor", native_enum=False)
    )
    # Obligatorio si condicion_pago=credito (accounting lo usa al pagar).
    plazo_dias_credito: Mapped[int | None] = mapped_column(nullable=True)
    afecto_igv: Mapped[bool] = mapped_column(Boolean, default=True)
    sujeto_spot: Mapped[bool] = mapped_column(Boolean, default=False)
    porcentaje_deteccion: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
