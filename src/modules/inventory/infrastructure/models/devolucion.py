"""devolucion: producto que se va o que vuelve, con una razón (RN-INV-019).

Cubre los dos casos que **no** tienen camino hoy:

- **A proveedor**: la mercadería sale del almacén y viaja con su propia
  guía de remisión (es un traslado que SUNAT quiere declarado). Dispara
  `inventory.devolucion_a_proveedor` para que `purchases` gestione el
  reclamo o la nota de crédito.
- **De cliente**: la mercadería entra al almacén, y `destino` decide qué
  pasa con ella: `reintegro` la suma a disponible, `desecho`/`auditoria` la
  aparta como merma.

La devolución **sucursal → central sigue siendo una transferencia** (ADR-020,
`transferencia` es genérica por almacén origen/destino): tiene despacho,
tránsito y recepción con diferencias, que es exactamente lo que ya está
construido. Modelarla otra vez acá sería un segundo camino para el mismo
movimiento y dos lugares donde el stock puede quedar distinto.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin

# Quién devuelve, que es también lo que decide la dirección del stock.
ORIGEN_DEVOLUCION = Enum(
    "proveedor",
    "cliente",
    name="origen_devolucion",
    native_enum=False,
)

MOTIVO_DEVOLUCION = Enum(
    "vencido",
    "dañado",
    "incumplimiento_plazo",
    "no_requerido",
    "error_solicitud",
    "duplicidad",
    name="motivo_devolucion",
    native_enum=False,
)

# Qué se hace con lo que vuelve. No aplica a la devolución a proveedor: eso
# se va y deja de ser problema del almacén.
DESTINO_DEVOLUCION = Enum(
    "desecho",
    "auditoria",
    "reintegro",
    name="destino_devolucion",
    native_enum=False,
)

ESTADO_DEVOLUCION = Enum(
    "registrada",
    "anulada",
    name="estado_devolucion",
    native_enum=False,
)


class Devolucion(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "devolucion"

    almacen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("almacen.id"))
    origen: Mapped[str] = mapped_column(ORIGEN_DEVOLUCION)
    # `proveedor_id` o `cliente_id` según `origen`. Sin FK: apunta a tablas
    # de dos módulos distintos, y una FK desde `inventory` a `sales` o a
    # `purchases` es justo lo que el event bus existe para evitar.
    referencia_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    motivo: Mapped[str] = mapped_column(MOTIVO_DEVOLUCION)
    # NULL en la devolución a proveedor: nada vuelve al estante.
    destino: Mapped[str | None] = mapped_column(DESTINO_DEVOLUCION, nullable=True)
    estado: Mapped[str] = mapped_column(ESTADO_DEVOLUCION, default="registrada")
    # A quién se dirige el reporte (RN-INV-020): almacén si devolvemos al
    # proveedor, comercial si devuelve un cliente. Se deriva del origen y se
    # guarda porque el reporte es del momento, no del criterio de hoy.
    reporte_dirigido_a: Mapped[str] = mapped_column(String(20))
    observacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    registrado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    anulado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    anulada_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
