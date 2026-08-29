"""Marcación: una fila por cada toque del pad, con su evidencia.

`asistencia` sigue siendo la fila-resumen del día (RN-RRHH-009,
`UNIQUE(trabajador_id, fecha)`); esto cuelga de ella y es lo que RRHH mira
cuando algo no cuadra — quién firmó, desde qué terminal, con qué IP, a qué
distancia de la sucursal y con qué cara.

La anomalía (fuera de rango, sin evidencia) no se guarda como columna: se
deriva en el reporte comparando `distancia_m` contra
`sucursal.radio_marcaje_m`. Si mañana se corrige el radio de un local, el
histórico se reclasifica solo en vez de quedar congelado con un criterio
viejo (RN-RRHH-024).

La foto vive en la fila y no en S3: hoy no hay ninguna ruta de subida al
storage para RRHH y el volumen es chico (JPEG de ~40 KB, retención de unos
meses). `# ponytail: la foto vive en la fila; si el volumen crece, pasa a
S3 vía `Archivo` (`src/shared/models/archivo.py`).`
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, LargeBinary, Numeric, String
from sqlalchemy.orm import Mapped, deferred, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Marcacion(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "marcacion"

    asistencia_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("asistencia.id"), index=True
    )
    tipo: Mapped[str] = mapped_column(
        Enum("entrada", "salida", name="tipo_marcacion", native_enum=False)
    )
    momento: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Quién firmó (el usuario cuyo PIN se verificó), no el trabajador: son
    # la misma persona en el pad, pero una corrección de back-office puede
    # firmarla RRHH por otro motivo distinto al PIN.
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    # NULL = corrección de back-office (`ASISTENCIA_MARCAR`), no vino del
    # pad. Distinguir esto es el propósito entero de la tabla.
    terminal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("terminal_marcaje.id"), nullable=True
    )
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    ubicacion_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    ubicacion_lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    distancia_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # `deferred`: el reporte lista decenas de marcaciones y no necesita el
    # binario en cada fila — se pide aparte, marcación por marcación.
    foto: Mapped[bytes | None] = deferred(
        mapped_column(LargeBinary, nullable=True)
    )
