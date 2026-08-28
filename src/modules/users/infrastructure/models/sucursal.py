"""Sucursal/local: espacio físico donde una empresa opera una marca (solo una)."""

import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import (
    JsonB,
    SoftDeleteMixin,
    TimestampMixin,
    UbicacionMixin,
    UuidPkMixin,
)


class Sucursal(
    Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin, UbicacionMixin
):
    __tablename__ = "sucursal"

    marca_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("marca.id"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    nombre: Mapped[str] = mapped_column(String(100))
    direccion: Mapped[str] = mapped_column(String(255))
    estado: Mapped[str] = mapped_column(
        Enum("activa", "inactiva", name="estado_sucursal", native_enum=False),
        default="activa",
    )
    # `propia` paga predial/arbitrios (RN-IMP-004).
    tenencia: Mapped[str] = mapped_column(
        Enum(
            "propia",
            "alquilada",
            "del_grupo",
            name="tenencia_sucursal",
            native_enum=False,
        )
    )
    # Disponibilidad al público; puede variar por día (glosario: Horario de
    # atención). El horario laboral de cada trabajador NO vive aquí.
    horario_atencion: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    # Radio en metros para observar (nunca bloquear) el marcaje de asistencia
    # (RN-RRHH-024, ADR-073). NULL = esta sucursal no evalúa distancia — el
    # GPS de una tablet bajo techo se equivoca por decenas de metros, así que
    # el valor nace vacío y cada local lo activa cuando le sirve.
    radio_marcaje_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
