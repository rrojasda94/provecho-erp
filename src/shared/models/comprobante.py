"""Comprobante: entidad transversal — sirve a `sales` emitiendo y a
`purchases`/`accounting` recibiendo. Vive en `shared`, no en un módulo
dueño único (Clean Architecture: ningún módulo importa el dominio de
otro).

`compra_id` queda sin FK a propósito — referencia `orden_compra.id`, dominio
de `purchases`; un FK cruzaría el módulo dueño único (CLAUDE.md: nunca
importar el dominio de otro módulo), mismo criterio que
`accounting.MovimientoDinero.proveedor_id`/`orden_compra_id`. El conjunto
válido de `tipo` según `direccion` (RN-CPP-001/002) se valida en el
dominio, no en el esquema.
"""

import uuid

from sqlalchemy import (
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class Comprobante(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "comprobante"
    __table_args__ = (
        UniqueConstraint("empresa_id", "serie", "correlativo"),
        # Una venta dividida tiene varios comprobantes: se busca por
        # (venta, grupo) al cobrar cada cuenta.
        Index("ix_comprobante_venta_grupo", "venta_id", "grupo_cobro"),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    # Si direccion=emitido.
    venta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("venta.id"), nullable=True
    )
    # Cuenta de la venta que este comprobante documenta (RN-COM-018). Una
    # venta dividida entre varios pagadores emite un comprobante por grupo,
    # por eso `venta_id` dejó de ser único. Vale 1 en toda venta sin dividir.
    grupo_cobro: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    # Receptor tecleado en caja cuando no hay `cliente` registrado: el PDV
    # pide DNI o RUC al cobrar y eso decide boleta/factura (RN-CPP-003).
    # Cuando vienen informados ganan sobre `venta.cliente_id` al armar el
    # envío a SUNAT; si están vacíos se usa el cliente de la venta como antes.
    receptor_num_doc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    receptor_nombre: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    # --- Emisión electrónica (solo direccion=emitido) ------------------------
    # `pendiente` nace al cobrar; la cola lo lleva a `aceptado`/`rechazado`.
    # `error` = fallo de transporte, reintentable. Un comprobante recibido
    # (compra) se queda en `no_aplica`: no lo emitimos nosotros.
    estado_emision: Mapped[str] = mapped_column(
        Enum(
            "no_aplica",
            "pendiente",
            "aceptado",
            "rechazado",
            "error",
            name="estado_emision_comprobante",
            native_enum=False,
        ),
        default="no_aplica",
    )
    # Hash del documento devuelto por el proveedor (respaldo ante SUNAT).
    hash_proveedor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Motivo del último rechazo/error, para mostrar sin abrir el JSON.
    detalle_emision: Mapped[str | None] = mapped_column(Text, nullable=True)
    intentos_emision: Mapped[int] = mapped_column(Integer, default=0)
    respuesta_proveedor: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
