"""alerta_pedido: un pedido que superó su tiempo y sigue en cocina.

No es un log: es el registro operativo de que algo se demoró, con lo que
hacía falta para entenderlo (cuánto tardó, contra qué umbral, en qué estado
estaba) y para cerrarlo (quién lo atendió y cuándo). El reporte
`pedidos_demorados` del tablero lee esta tabla.

Una fila por venta y umbral: la revisión es idempotente, así que reintentar
la tarea —o que el barrido periódico pase por encima de la tarea puntual—
nunca duplica la alerta.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class AlertaPedido(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "alerta_pedido"
    __table_args__ = (
        # La idempotencia vive en el esquema, no solo en el caso de uso: dos
        # workers revisando la misma venta a la vez no pueden crear dos.
        UniqueConstraint("venta_id", "minutos_umbral", name="uq_alerta_pedido_venta"),
    )

    venta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venta.id"), index=True)
    # Se copia de la venta en vez de derivarla por join: el reporte agrupa
    # por sucursal y no tiene por qué cargar la venta entera.
    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    # Contra qué umbral se disparó. Va en la fila porque el parámetro es
    # editable (`parametro_empresa`): subirlo mañana no puede reescribir la
    # historia de lo que en su momento se consideró demora.
    minutos_umbral: Mapped[int] = mapped_column(Integer)
    minutos_transcurridos: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    # Qué le faltaba al pedido al alertar: `pendiente` (cocina ni lo empezó)
    # pesa distinto que `en_preparacion` (lo está haciendo y no llega).
    estado_al_alertar: Mapped[str] = mapped_column(String(20))
    items_pendientes: Mapped[int] = mapped_column(Integer)

    # Cierre. NULL = sigue abierta; el reporte las separa por esto.
    atendida_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    atendida_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    nota: Mapped[str | None] = mapped_column(String(300), nullable=True)
