"""Plan de producción: cronograma fijo por línea/turno, o el hueco que un
ajuste por necesidad reserva sobre la marcha (RN-PRD-007/012).

`turno` y `linea_produccion` son texto libre y no un catálogo con FK:
`turno_sucursal` (RRHH) está atado a una sucursal, y una cocina de
producción central no siempre tiene una — forzar esa FK obligaría a un
almacén sin sucursal a inventarse una. La exclusividad real la da el
`UniqueConstraint` de abajo, no un catálogo.
"""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class PlanProduccion(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "plan_produccion"

    __table_args__ = (
        # RN-PRD-012: una línea, un tipo de receta por turno — no dos planes
        # compitiendo por la misma línea el mismo turno del mismo día.
        UniqueConstraint("almacen_id", "fecha", "turno", "linea_produccion"),
        CheckConstraint(
            "origen IN ('cronograma_fijo', 'ajuste_por_necesidad')",
            name="origen_plan_produccion",
        ),
        CheckConstraint(
            "estado IN ('planificado', 'en_ejecucion', 'cerrado')",
            name="estado_plan_produccion",
        ),
    )

    almacen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("almacen.id"))
    fecha: Mapped[date] = mapped_column(Date)
    turno: Mapped[str] = mapped_column(String(30))
    linea_produccion: Mapped[str] = mapped_column(String(100))
    origen: Mapped[str] = mapped_column(
        Enum(
            "cronograma_fijo", "ajuste_por_necesidad",
            name="origen_plan_produccion", native_enum=False,
        ),
        default="cronograma_fijo",
    )
    estado: Mapped[str] = mapped_column(
        Enum(
            "planificado", "en_ejecucion", "cerrado",
            name="estado_plan_produccion", native_enum=False,
        ),
        default="planificado",
    )
    # Nullable: un plan `ajuste_por_necesidad` lo crea el listener de
    # `inventory.stock_bajo_minimo`, sin ningún humano detrás (RN-PRD-007) —
    # mismo criterio que `orden_produccion.creado_por`.
    creado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
