"""guia_remision: el documento que acompaña a la mercadería en la carretera.

Cuelga de `transferencia` y no de `venta` porque lo que la guía declara es
un **traslado**, y el traslado es un hecho de inventario (RN-GDR-002: la
emite el área de almacén). Vive en `inventory` por eso mismo: emitirla desde
`sales` obligaría a importar el dominio de inventory para saber qué salió,
de qué almacén y en qué cantidad.

Serie y correlativo son **propios del almacén** (`T001-…`), no los del punto
de venta: la caja no emite guías y colgarlas de su serie mezclaría dos
numeraciones que SUNAT lleva por separado.

Los datos del chofer y del vehículo viajan acá, sin entidad `vehiculo`: el
grupo no tiene flota propia ni operación de reparto con ruteo (ver ROADMAP
→ Deuda técnica), y una tabla de vehículos sería un formulario que nadie
mantiene. Cuando exista flota, `vehiculo_placa` se reemplaza por su FK.
"""

import datetime
import uuid
from decimal import Decimal

from sqlalchemy import (
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin

# Catálogo 20 de SUNAT — motivo del traslado. Solo los que el negocio
# produce hoy: mover insumos entre sus propios almacenes y devolver al
# central. El catálogo completo tiene catorce y el resto describe
# operaciones que este ERP no genera (importación, exportación, consignación).
MOTIVO_TRASLADO = Enum(
    "01",  # Venta
    "04",  # Traslado entre establecimientos de la misma empresa
    "13",  # Otros
    "18",  # Traslado emisor itinerante
    name="motivo_traslado_guia",
    native_enum=False,
)

# Catálogo 18 — modalidad. `02` (privado) es la de siempre acá: la
# mercadería la lleva alguien del grupo en su propio vehículo.
MODALIDAD_TRASLADO = Enum(
    "01",  # Transporte público (un tercero presta el servicio)
    "02",  # Transporte privado
    name="modalidad_traslado_guia",
    native_enum=False,
)


class GuiaRemision(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "guia_remision"
    __table_args__ = (
        # Nombre explícito: la convención de `database.py` rinde
        # `uq_<tabla>_<primera columna>`, que para tres columnas queda como
        # `uq_guia_remision_empresa_id` y no coincide con el nombre que la
        # migración le puso. Sin esto, `alembic check` propone borrar y
        # recrear la misma constraint en cada corrida.
        UniqueConstraint(
            "empresa_id",
            "serie",
            "correlativo",
            name="uq_guia_remision_empresa_id_serie_correlativo",
        ),
        # Un traslado, una guía: reemitir sobre la misma transferencia
        # produciría dos documentos que declaran la misma mercadería.
        UniqueConstraint("transferencia_id"),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    transferencia_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transferencia.id")
    )
    serie: Mapped[str] = mapped_column(String(10))
    correlativo: Mapped[int] = mapped_column(Integer)
    fecha_inicio_traslado: Mapped[datetime.date] = mapped_column(Date)
    motivo_traslado: Mapped[str] = mapped_column(MOTIVO_TRASLADO, default="04")
    modalidad_traslado: Mapped[str] = mapped_column(MODALIDAD_TRASLADO, default="02")
    # SUNAT lo exige y no se puede derivar: el peso de un SKU no está en el
    # catálogo, así que lo declara quien carga el vehículo.
    peso_bruto_kg: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    # RUC del emisor y del receptor (RN-GDR-001). En un traslado entre
    # establecimientos propios son el mismo, y así debe verse: que coincidan
    # es lo que sustenta el motivo `04`.
    ruc_emisor: Mapped[str] = mapped_column(String(11))
    ruc_receptor: Mapped[str] = mapped_column(String(11))
    # Direcciones congeladas al emitir: si el almacén se muda después, la
    # guía tiene que seguir diciendo de dónde salió esa carga.
    lugar_origen: Mapped[str] = mapped_column(String(255))
    lugar_destino: Mapped[str] = mapped_column(String(255))
    chofer_nombres: Mapped[str] = mapped_column(String(120))
    chofer_apellidos: Mapped[str] = mapped_column(String(120))
    chofer_num_doc: Mapped[str] = mapped_column(String(15))
    chofer_licencia: Mapped[str] = mapped_column(String(20))
    vehiculo_placa: Mapped[str] = mapped_column(String(10))
    emitida_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    observacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # --- Emisión electrónica (mismo juego que `comprobante`) -----------------
    # `pendiente` nace al emitir; la cola lo lleva a `aceptado`/`rechazado`.
    # `error` = fallo de transporte, reintentable.
    estado_emision: Mapped[str] = mapped_column(
        Enum(
            "pendiente",
            "aceptado",
            "rechazado",
            "error",
            name="estado_emision_guia",
            native_enum=False,
        ),
        default="pendiente",
    )
    hash_proveedor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    detalle_emision: Mapped[str | None] = mapped_column(Text, nullable=True)
    intentos_emision: Mapped[int] = mapped_column(Integer, default=0)
    respuesta_proveedor: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
