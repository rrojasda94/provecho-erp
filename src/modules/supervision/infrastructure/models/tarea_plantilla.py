"""Plantilla de tarea de supervisión: qué se hace, en qué momento, con qué
frecuencia y con qué checklist. `generacion.py` la usa cada día para fabricar
la `TareaInstancia` que el trabajador realmente marca.

`sucursal_id`/`marca_id`: una plantilla de sucursal manda solo ahí; una de
marca (`sucursal_id` NULL) aplica a todas las sucursales de esa marca — así
una cadena no repite treinta veces el mismo checklist de apertura.
"""

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class TareaPlantilla(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "tarea_plantilla"

    __table_args__ = (
        CheckConstraint(
            "sucursal_id IS NOT NULL OR marca_id IS NOT NULL",
            name="alcance_tarea_plantilla",
        ),
        CheckConstraint("momento IN ('apertura', 'cierre')", name="momento_tarea_plantilla"),
        CheckConstraint(
            "frecuencia IN ('diaria', 'interdiaria', 'semanal', 'mensual')",
            name="frecuencia_tarea_plantilla",
        ),
        CheckConstraint(
            "dia_semana IS NULL OR (dia_semana >= 0 AND dia_semana <= 6)",
            name="dia_semana_tarea_plantilla",
        ),
        CheckConstraint(
            "dia_mes IS NULL OR (dia_mes >= 1 AND dia_mes <= 28)",
            name="dia_mes_tarea_plantilla",
        ),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    marca_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("marca.id"), nullable=True)
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )
    categoria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categoria_tarea.id"))
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    momento: Mapped[str] = mapped_column(
        Enum("apertura", "cierre", name="momento_tarea_plantilla", native_enum=False)
    )
    # Se puede repetir: dos tareas con el mismo orden se hacen en paralelo
    # (ej. encender las luces mientras se trae lo de limpieza).
    orden: Mapped[int] = mapped_column(Integer, default=1)
    frecuencia: Mapped[str] = mapped_column(
        Enum(
            "diaria", "interdiaria", "semanal", "mensual",
            name="frecuencia_tarea_plantilla", native_enum=False,
        )
    )
    dia_semana: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dia_mes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Ancla de la interdiaria y piso de la generación: nunca se fabrica una
    # instancia de un día anterior a esta fecha.
    fecha_inicio: Mapped[date] = mapped_column(Date)
    requiere_foto: Mapped[bool] = mapped_column(Boolean, default=False)
    # list[str]: el enunciado de cada ítem. La instancia lo copia y le agrega
    # `hecho` — la plantilla no lleva estado, es reutilizable todos los días.
    checklist: Mapped[list] = mapped_column(JsonB, default=list)
    # Responsable por defecto; la instancia lo hereda y se puede reasignar
    # cada día. Sin responsable, la instancia nace sin asignar.
    asignado_a: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
