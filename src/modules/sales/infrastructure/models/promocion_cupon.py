"""Promoción de cupón: la campaña que emite un cupón por cliente.

Cuelga de `grupo_id` y no de `empresa_id` porque el cupón se le da a un
`cliente`, que es transversal al grupo (RN-PTS-001). Una promoción que
viviera en una empresa dejaría al cliente con un cupón que no puede usar en
el local de al lado, que es exactamente lo contrario de lo que busca.

No es la `promocion` de `data-model.md` §6 —esa liga una lista de precios,
material promocional y guion de atención, y todavía no existe—. Esta es más
chica y hace una sola cosa: un porcentaje, una vigencia y un interruptor
para apagarla.

`estado` es ese interruptor: la empresa se reserva el derecho de terminar la
promoción en cualquier momento, y eso tiene que ser un cambio de fila, no un
despliegue.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class PromocionCupon(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "promocion_cupon"
    __table_args__ = (UniqueConstraint("grupo_id", "nombre"),)

    grupo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("grupo.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    descuento_porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    # Fin de campaña. Pasada esta fecha no se emite ningún cupón nuevo; los
    # ya emitidos siguen valiendo hasta SU propia fecha (el cliente ya
    # cumplió su parte del trato).
    vigente_hasta: Mapped[date] = mapped_column(Date())
    # Cuántos días vale cada cupón desde que se emite.
    vigencia_cupon_dias: Mapped[int] = mapped_column()
    estado: Mapped[str] = mapped_column(
        Enum("activa", "terminada", name="estado_promocion_cupon", native_enum=False),
        default="activa",
    )
    terminada_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    terminada_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
