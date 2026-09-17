"""La tarea del día: lo que el trabajador realmente ve y marca en su
pantalla. Puede venir de una plantilla (`plantilla_id`) o haberse creado a
mano (`plantilla_id` NULL) — un imprevisto que el supervisor agrega ese día
sin tener que crear una plantilla que no se va a repetir.

La foto vive acá, comprimida por el servidor y sin EXIF (`application/
fotos.py`), `deferred` para no viajar en cada listado — mismo patrón que
`delivery.Entrega.evidencia_foto` y la foto de marcación de `rrhh`.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    text,
)
from sqlalchemy.orm import Mapped, deferred, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class TareaInstancia(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "tarea_instancia"

    __table_args__ = (
        # Generación idempotente: una plantilla no fabrica dos instancias el
        # mismo día en la misma sucursal aunque el barrido corra dos veces.
        # `sucursal_id` es parte de la clave porque una plantilla de marca
        # (`sucursal_id IS NULL` en la plantilla) genera una instancia por
        # cada sucursal de la marca el mismo día — sin la sucursal en la
        # clave, la segunda sucursal se veía como "ya generada" por la
        # primera. Parcial porque una tarea manual (`plantilla_id IS NULL`)
        # sí puede repetirse el mismo día — no tiene plantilla con la que
        # chocar.
        Index(
            "uq_tarea_instancia_plantilla_sucursal_fecha",
            "plantilla_id",
            "sucursal_id",
            "fecha",
            unique=True,
            sqlite_where=text("plantilla_id IS NOT NULL"),
            postgresql_where=text("plantilla_id IS NOT NULL"),
        ),
        CheckConstraint("momento IN ('apertura', 'cierre')", name="momento_tarea_instancia"),
        CheckConstraint(
            "estado IN ('pendiente', 'completada', 'vencida')",
            name="estado_tarea_instancia",
        ),
    )

    plantilla_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tarea_plantilla.id"), nullable=True
    )
    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    fecha: Mapped[date] = mapped_column(Date)
    momento: Mapped[str] = mapped_column(
        Enum("apertura", "cierre", name="momento_tarea_instancia", native_enum=False)
    )
    orden: Mapped[int] = mapped_column(Integer, default=1)
    nombre: Mapped[str] = mapped_column(String(120))
    categoria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categoria_tarea.id"))
    requiere_foto: Mapped[bool] = mapped_column(Boolean, default=False)
    # [{"texto": str, "hecho": bool}] — el trabajador solo puede tocar
    # `hecho`; `texto` es el enunciado copiado de la plantilla al generar.
    checklist: Mapped[list] = mapped_column(JsonB, default=list)
    asignado_a: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    estado: Mapped[str] = mapped_column(
        Enum(
            "pendiente", "completada", "vencida",
            name="estado_tarea_instancia", native_enum=False,
        ),
        default="pendiente",
    )
    completada_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completada_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    foto: Mapped[bytes | None] = deferred(mapped_column(LargeBinary, nullable=True))
    # Fecha de captura leída del EXIF (`DateTimeOriginal`), en hora del
    # negocio. `None` = la foto no traía ese metadato (no es indicio de
    # fraude por sí solo — muchas apps de cámara lo omiten).
    foto_tomada_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # `None` = sin foto o sin EXIF que comparar; `True`/`False` = la foto
    # cayó dentro/fuera de la tolerancia de `foto_tomada_at` vs. el momento
    # de completar. Nunca bloquea completar (RN-SUP-006): queda marcada para
    # que el supervisor la revise en el informe.
    foto_valida: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    observacion: Mapped[str | None] = mapped_column(String(255), nullable=True)
