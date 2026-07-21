"""Apertura de caja (PROC-CTB-002). Inicia la cadena de custodia inversa
(RN-MDP-002): contabilidad/encargado → cajero.
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
    # Relevo autenticado por ambas partes con usuario+PIN (validado en el
    # dominio, no en el esquema).
    relevo_encargado_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
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
