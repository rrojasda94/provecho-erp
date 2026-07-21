"""Comprobante: entidad transversal — sirve a `sales` emitiendo y a
`purchases`/`accounting` recibiendo. Vive en `shared`, no en un módulo
dueño único (Clean Architecture: ningún módulo importa el dominio de
otro).

`compra_id` queda sin FK — `purchases` aún no modela sus tablas de
recepción. El conjunto válido de `tipo` según `direccion` (RN-CPP-001/002)
se valida en el dominio, no en el esquema.
"""

import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class Comprobante(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "comprobante"
    __table_args__ = (UniqueConstraint("empresa_id", "serie", "correlativo"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    # Si direccion=emitido.
    venta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("venta.id"), nullable=True
    )
    # Si direccion=recibido — FK diferida (purchases sin tablas de recepción aún).
    compra_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    # Origen de la serie si direccion=emitido.
    punto_venta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("punto_venta.id"), nullable=True
    )
    direccion: Mapped[str] = mapped_column(
        Enum("emitido", "recibido", name="direccion_comprobante", native_enum=False)
    )
    tipo: Mapped[str] = mapped_column(
        Enum(
            "boleta",
            "factura",
            "nc",
            "rhe",
            "ticket_compra",
            name="tipo_comprobante",
            native_enum=False,
        )
    )
    # Snapshot de punto_venta.serie_boleta/serie_factura al emitir —
    # inmutable aunque el punto de venta cambie de serie después.
    serie: Mapped[str] = mapped_column(String(10))
    correlativo: Mapped[int] = mapped_column(Integer)
    sustento: Mapped[str] = mapped_column(
        Enum(
            "efectivo",
            "voucher_medio_pago",
            "movimiento_bancario",
            "contrato_credito",
            name="sustento_comprobante",
            native_enum=False,
        )
    )
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    estado_nubefact: Mapped[str | None] = mapped_column(String(30), nullable=True)
    respuesta_nubefact: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
