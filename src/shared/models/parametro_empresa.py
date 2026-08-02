"""ParametroEmpresa: valor operativo configurable por empresa (ADR-014).

El área propone el cambio desde su propio módulo, pero **el valor no surte
efecto hasta que Gerencia lo aprueba** en su sección de aprobaciones (puede
aceptar, rechazar, o modificar el valor al aprobar). Recién ahí el módulo
consumidor lo lee.

Cada propuesta es una fila; aprobar la nueva marca la anterior como
`reemplazado`. El historial (quién propuso, quién resolvió, cuándo, valor
anterior y nuevo) queda en la propia tabla — no hace falta `audit_log`.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin

ESTADOS = ("propuesto", "vigente", "rechazado", "reemplazado")


class ParametroEmpresa(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "parametro_empresa"
    __table_args__ = (
        # Un solo valor vigente por empresa/modulo/codigo; las propuestas y el
        # historial conviven sin chocar.
        Index(
            "uq_parametro_empresa_vigente",
            "empresa_id",
            "modulo",
            "codigo",
            unique=True,
            sqlite_where=text("estado = 'vigente'"),
            postgresql_where=text("estado = 'vigente'"),
        ),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    modulo: Mapped[str] = mapped_column(String(50))  # ej. "inventory"
    codigo: Mapped[str] = mapped_column(String(50))  # ej. "margen_error_ajuste"
    # Forma libre por código, pero toda magnitud viaja con su unidad
    # (RN-GER-010, `src/shared/magnitudes.py`): {"monto":"500.00","divisa":"PEN"},
    # {"minimo":"1500.00","maximo":"2200.00","divisa":"PEN"},
    # {"cantidad":"5.000","unidad_medida_id":"..."}. Los adimensionales van
    # sueltos: {"frecuencia":"mensual"}, {"dias":5}, {"porcentaje":2.5}.
    valor: Mapped[dict[str, Any]] = mapped_column(JsonB)
    # Magnitud ya formateada con su unidad ("S/ 2000.00", "5.000 Kilo"), como
    # se le mostró a Gerencia al decidir. Se congela con la fila: renombrar la
    # UdM después no reescribe lo que se aprobó. NULL si es adimensional.
    valor_display: Mapped[str | None] = mapped_column(String(120), nullable=True)

    estado: Mapped[str] = mapped_column(
        Enum(*ESTADOS, name="estado_parametro_empresa", native_enum=False),
        default="propuesto",
    )
    propuesto_por_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)

    resuelto_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    resuelto_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    motivo_rechazo: Mapped[str | None] = mapped_column(Text, nullable=True)
