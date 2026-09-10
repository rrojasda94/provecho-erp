"""Repartidor propio: un trabajador con cuenta que reparte a pie, en
bicicleta, moto o auto de la empresa (ADR-098, distinto del repartidor de
plataforma externa de RN-PER-003, que no es recurso propio).

`usuario_id` es columna propia y no derivada como en `trabajador` (ADR-070):
acá hace falta filtrar "mis rutas" por `usuario_id` en cada request del
celular del repartidor, y una subconsulta correlacionada en ese camino
caliente es peor que la fila que puede quedar desincronizada si alguien
cambia el `usuario_id` de una persona sin pasar por acá — algo que hoy no
tiene pantalla y que la única vía de alta (`repartidores.crear`) fija una
sola vez al dar de alta.
"""

import uuid

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin
from src.modules.delivery.domain import rules


class Repartidor(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "repartidor"

    __table_args__ = (
        Index("ix_repartidor_sucursal_activo", "sucursal_id", "activo"),
        CheckConstraint(
            "vehiculo_tipo IN ({})".format(", ".join(f"'{v}'" for v in rules.VEHICULOS)),
            name="vehiculo_tipo_repartidor",
        ),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    # Sucursal base del repartidor — de dónde sale por defecto. No limita
    # qué rutas puede llevar (eso lo decide quien despacha al crear la
    # ruta), solo dónde se lo espera.
    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    trabajador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trabajador.id"), unique=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"), unique=True)
    vehiculo_tipo: Mapped[str] = mapped_column(
        Enum(*rules.VEHICULOS, name="vehiculo_tipo_repartidor", native_enum=False)
    )
    placa: Mapped[str | None] = mapped_column(String(10), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
