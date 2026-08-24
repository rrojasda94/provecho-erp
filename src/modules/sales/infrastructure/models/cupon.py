"""Cupón de descuento: un beneficio nominal, de un solo uso.

Dos únicos por `(promocion_id, ...)` y no por columna suelta:

- `(promocion_id, cliente_id)` es «un cupón por cliente», y vive en la base
  a propósito. Dos registros simultáneos del mismo cliente desde dos
  teléfonos chocan contra el índice en vez de emitir dos cupones — una
  verificación en Python no cubre esa carrera.
- `(promocion_id, codigo)` sostiene la búsqueda por código en caja.

`estado` no incluye `vencido`: vencer es una comparación de fechas, no un
hecho que alguien registre. Un estado que hay que barrer con una tarea
periódica queda mal justo cuando la tarea no corrió — `rules.cupon_vigente`
lo deriva de `vigente_hasta` y siempre dice la verdad.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Cupon(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "cupon"
    # Los dos nombres van a mano: la convención de `NAMING_CONVENTION` los
    # arma con la PRIMERA columna, y los dos empiezan por `promocion_id` —
    # sin nombrarlos, los dos se llamarían `uq_cupon_promocion_id` y
    # Postgres rechazaría el segundo al crear la tabla.
    __table_args__ = (
        UniqueConstraint("promocion_id", "cliente_id", name="uq_cupon_promocion_cliente"),
        UniqueConstraint("promocion_id", "codigo", name="uq_cupon_promocion_codigo"),
    )

    promocion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("promocion_cupon.id"))
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cliente.id"))
    # El número de documento del cliente (decisión del usuario, 2026-08-24).
    # Que el código sea algo que el cliente ya sabe es lo que hace que no
    # tenga nada que recordar ni guardar; el costo está anotado en ADR-060.
    codigo: Mapped[str] = mapped_column(String(20))
    estado: Mapped[str] = mapped_column(
        Enum("activo", "canjeado", name="estado_cupon", native_enum=False),
        default="activo",
    )
    vigente_hasta: Mapped[date] = mapped_column(Date())
    # Indexada: es por donde se lee «qué cupón descontó esta venta» al
    # revisar el reporte de descuentos. Las otras dos FK no la necesitan —
    # `cliente_id` ya va en el único y `canjeado_por` no se filtra.
    venta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("venta.id"), index=True, nullable=True
    )
    canjeado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    canjeado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
