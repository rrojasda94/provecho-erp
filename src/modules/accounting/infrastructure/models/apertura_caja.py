"""Apertura de caja (PROC-CTB-002): el cajero cuenta el fondo con el que
arranca su turno y verifica los terminales.

La abre **él solo** (RN-MDP-008, ADR-048): lo que prueba cuánto había es el
conteo por denominación, no una firma. La cadena de custodia firmada
(RN-MDP-002) empieza al cerrar, en `custodia_efectivo`.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class AperturaCaja(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "apertura_caja"

    punto_venta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("punto_venta.id"))
    cajero_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    # Quién firmó la entrega del fondo, cuando la apertura la exigía
    # (hasta ADR-048). NULL en las aperturas nuevas: el cajero abre solo y
    # no hay contraparte. Se conserva porque las aperturas anteriores sí
    # tienen firma y esa evidencia no se reescribe.
    relevo_encargado_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    monto_apertura: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # Conteo por billete/moneda (RN-POS-003).
    detalle_denominaciones: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    # No se apertura sin registrarla si existe — notifica a contabilidad
    # y gerencia (accounting.apertura_caja_registrada).
    diferencia_reportada: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    # Serie/código de comercio de cada POS de tarjeta (RN-POS-010).
    pos_verificados: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
