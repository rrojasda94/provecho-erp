"""asiento_omitido: un asiento que el sistema decidió NO escribir.

El asiento automático nunca bloquea la operación que lo originó — una venta
no se cae porque contabilidad no esté configurada, y eso está bien. El costo
de esa decisión es que **el balance puede quedar vacío sin que nadie se
entere**: el 2026-09-05 se descubrió que ninguna empresa tenía plan de
cuentas ni periodo abierto, así que ningún asiento automático del ERP entero
había entrado nunca, y el único rastro era un `log.info` que además decía el
motivo equivocado.

Es la misma tabla que `incidencia_inventario`, por la misma razón y con la
misma forma: la omisión correcta tiene que quedar consultable con lo que hace
falta para arreglarla.

Sin cierre (`atendida_at`) a propósito, igual que su gemela: el reporte va
por rango de fechas y una configuración rota vuelve a aparecer mañana, que es
la señal correcta.
"""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin

# Por qué se omitió. Cada uno se arregla en un lugar distinto: `periodo_cerrado`
# es una decisión de contabilidad (el mes ya se cerró y llegó un hecho de ese
# mes), `sin_cuentas` es plan de cuentas sin importar, y `sin_plantilla` es un
# evento que nadie mapeó todavía — deuda del ERP, no de la empresa.
#
# No están `duplicado` ni `monto_cero`: los dos son omisiones **correctas y
# esperadas** —el evento se reprocesó, o el hecho no movió plata— y anotarlas
# convertiría la tabla en ruido que nadie mira.
MOTIVO_OMISION = Enum(
    "periodo_cerrado",
    "sin_cuentas",
    "sin_plantilla",
    name="motivo_asiento_omitido",
    native_enum=False,
)


class AsientoOmitido(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "asiento_omitido"

    __table_args__ = (
        CheckConstraint(
            "motivo IN ('periodo_cerrado', 'sin_cuentas', 'sin_plantilla')",
            name="motivo_asiento_omitido",
        ),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    # El evento operativo que lo pedía (`sales.venta_confirmada`, ...).
    evento: Mapped[str] = mapped_column(String(64), index=True)
    # Id del documento de origen. String y no FK, igual que en
    # `incidencia_inventario`: los orígenes viven en otros módulos y una FK
    # sería justo el acoplamiento que el bus existe para evitar.
    referencia_origen: Mapped[str] = mapped_column(String(64), index=True)
    motivo: Mapped[str] = mapped_column(MOTIVO_OMISION)
    # La fecha con la que se habría asentado. Es la que dice en qué periodo
    # falta la plata, y no coincide con `created_at` cuando el evento llega
    # tarde.
    fecha: Mapped[date] = mapped_column(Date, index=True)
    # Qué falta exactamente: los códigos de cuenta ausentes, por ejemplo.
    detalle: Mapped[str | None] = mapped_column(String(300), nullable=True)
