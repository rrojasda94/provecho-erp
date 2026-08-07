"""incidencia_inventario: un movimiento que el sistema decidió NO hacer.

Cuando una venta se confirma sin almacén configurado, con un artículo sin
SKU activo o sin stock teórico que alcance, el listener **omite el consumo
y sigue** — la venta ya ocurrió y nunca se bloquea por inventario. Esa
decisión es correcta y es también el único punto del ERP donde el stock se
va de la realidad sin que nadie lo pida.

Hasta ahora la omisión solo salía por `log.warning`, que en la práctica es
no salir a ningún lado: nadie lee los logs de la aplicación buscando por
qué el queso no cuadra. Esta tabla la deja consultable con lo que hace
falta para arreglarla — qué documento la originó, qué artículo, y **por
qué** se omitió, que es lo que dice qué hay que corregir.

Sin cierre (`atendida_at`) a propósito: el reporte va por rango de fechas y
una configuración rota vuelve a aparecer mañana, que es la señal correcta.
Se agrega el día que haya que distinguir "ya lo arreglé" de "todavía no".
"""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin

# Qué documento operativo quedó sin su movimiento.
ORIGEN_INCIDENCIA = Enum(
    "venta",
    "orden_compra",
    "orden_produccion",
    name="origen_incidencia_inventario",
    native_enum=False,
)

# Por qué se omitió. Cada uno se arregla en un lugar distinto: `sin_almacen`
# es configuración de la sucursal, `sin_sku` es catálogo, y
# `stock_insuficiente` es el stock que ya venía mal.
TIPO_INCIDENCIA = Enum(
    "sin_almacen",
    "sin_sku",
    "stock_insuficiente",
    name="tipo_incidencia_inventario",
    native_enum=False,
)


class IncidenciaInventario(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "incidencia_inventario"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    origen: Mapped[str] = mapped_column(ORIGEN_INCIDENCIA)
    # Id del documento de origen. String y no FK: los tres orígenes viven en
    # módulos distintos y una FK a `venta` desde inventory sería justo el
    # acoplamiento que el event bus existe para evitar.
    referencia: Mapped[str] = mapped_column(String(64), index=True)
    tipo: Mapped[str] = mapped_column(TIPO_INCIDENCIA)

    # Nulos según el tipo: `sin_almacen` no tiene almacén (ese es el problema)
    # y `sin_sku` no tiene SKU.
    almacen_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("almacen.id"), nullable=True
    )
    articulo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("articulo.id"), nullable=True
    )
    sku_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sku.id"), nullable=True
    )
    # Lo que no se movió. Es la magnitud del desvío, no un dato informativo.
    cantidad: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    detalle: Mapped[str | None] = mapped_column(String(300), nullable=True)
