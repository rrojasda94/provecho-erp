"""Activo: equipamiento o vehículo de la empresa (data-model.md §Recursos).

`flota` y `repuesto_compatibilidad` quedan diferidos (deuda técnica, ver
`docs/roadmap/deuda/modulo-assets.md`): no hay reparto propio con flota que
los necesite hoy, y agregarlos habría sido un formulario sin quien lo llene.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin
from src.modules.assets.domain.rules import ESTADOS_ACTIVO, TIPOS_ACTIVO


class Activo(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "activo"

    __table_args__ = (
        CheckConstraint("tipo IN ('equipamiento', 'vehiculo')", name="tipo_activo"),
        CheckConstraint(
            "estado IN ('operativo', 'en_mantenimiento', 'de_baja')",
            name="estado_activo",
        ),
        UniqueConstraint("empresa_id", "id_interno", name="uq_activo_id_interno"),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    # Centro de labores del activo (RN-GEN-005 lo pide corregible por
    # pantalla). Nullable: un activo de administración puede no estar en
    # ningún local.
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sucursal.id"), nullable=True)
    tipo: Mapped[str] = mapped_column(Enum(*TIPOS_ACTIVO, name="tipo_activo", native_enum=False))
    # Lo teclea quien da de alta, igual que `articulo.id_interno`
    # (`inventory.crear_articulo`): pese a RN-GEN-005, hoy nadie en el ERP lo
    # autogenera — no hay generador que reusar.
    id_interno: Mapped[str] = mapped_column(String(8))
    nombre: Mapped[str] = mapped_column(String(150))
    # Texto libre y no FK a `inventory.categoria`: esa tabla es de artículos
    # inventariables (con SKU, stock, receta); un activo no vive en almacén
    # de artículos y forzar la FK habría atado dos catálogos que no son lo
    # mismo, solo por compartir el nombre "categoría".
    categoria: Mapped[str | None] = mapped_column(String(60), nullable=True)
    marca: Mapped[str | None] = mapped_column(String(60), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    numero_serie: Mapped[str | None] = mapped_column(String(80), nullable=True)
    etiqueta_codigo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fecha_compra: Mapped[date | None] = mapped_column(Date, nullable=True)
    valor_compra: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    vida_util_meses: Mapped[int | None] = mapped_column(nullable=True)
    # Sin FK: `proveedor` es dominio de `purchases` (CLAUDE.md — nunca
    # importar el dominio de otro módulo). Se resuelve, si hace falta, por
    # `purchases.application.queries_publicas.proveedor_para_guia`.
    proveedor_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    comprobante_compra_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comprobante.id"), nullable=True
    )
    # Sin FK: `trabajador` es dominio de `rrhh`. Se valida por
    # `rrhh.application.queries_publicas.trabajador_resumen`.
    responsable_trabajador_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    estado: Mapped[str] = mapped_column(
        Enum(*ESTADOS_ACTIVO, name="estado_activo", native_enum=False),
        default="operativo",
    )
    # Oculta de listados sin borrar (mismo criterio que `activo` en
    # data-model.md): un activo de baja sigue teniendo historial de
    # mantenimiento y documentos que no se puede perder.
    archivado: Mapped[bool] = mapped_column(Boolean, default=False)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
