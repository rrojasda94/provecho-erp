"""Mesa: puesto físico del salón de una sucursal (RN-MDC-001).

Vive en `sales` y no en `users` aunque sea mobiliario de la sucursal: quien
la usa y le da sentido es la toma de pedido (`venta.mesa_id`), y el módulo
dueño de la venta no puede importar el dominio de otro (CLAUDE.md). De
`users` solo se referencia `sucursal_id`, igual que hace `punto_venta`.

Reemplaza el uso de `venta.referencia_atencion` para el caso mesa: ese
campo sigue existiendo como texto libre para takeout/delivery ("Carlos",
"Rappi #1042"), pero el número de mesa ahora es un dato tipado y
consultable (mapa de mesas ocupadas, ventas por mesa).
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Mesa(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "mesa"
    # El número es el identificador que canta el personal; único dentro de
    # la sucursal, no del grupo.
    __table_args__ = (
        UniqueConstraint("sucursal_id", "numero", name="uq_mesa_sucursal_numero"),
    )

    # El mapa del salón se consulta por sucursal en cada refresco del PDV.
    sucursal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sucursal.id"), index=True
    )
    numero: Mapped[int] = mapped_column(Integer)
    # "Salón", "Terraza", "Barra" — agrupa el mapa de mesas. Libre porque
    # cada local nombra sus zonas distinto.
    zona: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Comensales que caben; referencia para el anfitrión, no un tope duro.
    capacidad: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Baja lógica sin borrar historia: una mesa retirada del salón deja de
    # ofrecerse en el PDV pero sus ventas pasadas siguen resolviendo.
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
