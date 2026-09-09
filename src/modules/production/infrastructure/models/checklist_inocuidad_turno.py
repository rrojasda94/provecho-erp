"""Checklist de inocuidad de turno: bioseguridad, superficies, limpieza
intermedia, equipos de frío y posible indicio de plaga (RN-CDP-002/005).

`estado` no lo decide quien registra el checklist: `application/
inocuidad.py::crear_checklist` lo calcula (aprobado solo si los tres
booleanos son true, ningún equipo de frío fuera de rango y sin indicio de
plaga) — la cocina no se autoaprueba escribiendo `estado=aprobado` a mano.

`turno` es texto libre, mismo criterio que `plan_produccion.turno`: una
cocina de producción central no siempre tiene sucursal, así que no hay FK a
`turno_sucursal` (RRHH).

Simplificación documentada: `orden_produccion` no registra en qué turno se
creó, así que `application/inocuidad.py::exigir_cocina_habilitada` no
compara por turno — usa el checklist más reciente del almacén para el día
(`created_at desc`). Una vez bloqueada la cocina, sigue bloqueada hasta que
un checklist nuevo la reapruebe, sea del mismo turno o de otro.
"""

import uuid
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class ChecklistInocuidadTurno(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "checklist_inocuidad_turno"

    __table_args__ = (
        UniqueConstraint("almacen_id", "fecha", "turno"),
        CheckConstraint(
            "estado IN ('aprobado', 'bloqueado')",
            name="estado_checklist_inocuidad_turno",
        ),
    )

    almacen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("almacen.id"))
    fecha: Mapped[date] = mapped_column(Date)
    turno: Mapped[str] = mapped_column(String(30))
    verificado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    bioseguridad_ok: Mapped[bool] = mapped_column(Boolean)
    superficies_ok: Mapped[bool] = mapped_column(Boolean)
    limpieza_intermedia_ok: Mapped[bool] = mapped_column(Boolean)
    # [{equipo, temperatura_c, rango_min, rango_max, dentro_rango}]. `equipo`
    # es texto libre: no hay catálogo de equipos de frío en el modelo de
    # datos. `dentro_rango` lo calcula el servidor (`domain.rules.
    # equipo_dentro_rango`), nunca lo manda el cliente.
    equipos_frio: Mapped[list] = mapped_column(JsonB, default=list)
    plaga_indicio: Mapped[bool] = mapped_column(Boolean, default=False)
    estado: Mapped[str] = mapped_column(
        Enum(
            "aprobado", "bloqueado",
            name="estado_checklist_inocuidad_turno", native_enum=False,
        ),
    )
