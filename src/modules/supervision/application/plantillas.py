"""Plantillas de tarea de supervisión: CRUD. `generacion.py` las consume a
diario; acá solo se administran."""

import uuid
from datetime import date

from src.modules.supervision.application.errors import NoEncontrado, ReglaNegocio
from src.modules.supervision.domain import rules
from src.modules.supervision.infrastructure.models import TareaPlantilla
from src.modules.supervision.infrastructure.repositories import TareaPlantillaRepo


def crear_plantilla(
    session,
    *,
    empresa_id: uuid.UUID,
    categoria_id: uuid.UUID,
    nombre: str,
    momento: str,
    frecuencia: str,
    fecha_inicio: date,
    orden: int = 1,
    descripcion: str | None = None,
    marca_id: uuid.UUID | None = None,
    sucursal_id: uuid.UUID | None = None,
    dia_semana: int | None = None,
    dia_mes: int | None = None,
    requiere_foto: bool = False,
    checklist: list[str] | None = None,
    asignado_a: uuid.UUID | None = None,
) -> TareaPlantilla:
    if marca_id is None and sucursal_id is None:
        raise ReglaNegocio("la plantilla necesita una marca o una sucursal")
    if momento not in rules.MOMENTOS:
        raise ReglaNegocio(f"momento inválido: {momento}")
    if frecuencia not in rules.FRECUENCIAS:
        raise ReglaNegocio(f"frecuencia inválida: {frecuencia}")
    if frecuencia == "semanal" and dia_semana is None:
        raise ReglaNegocio("la frecuencia semanal necesita dia_semana")
    if frecuencia == "mensual" and dia_mes is None:
        raise ReglaNegocio("la frecuencia mensual necesita dia_mes")
    plantilla = TareaPlantilla(
        empresa_id=empresa_id,
        marca_id=marca_id,
        sucursal_id=sucursal_id,
        categoria_id=categoria_id,
        nombre=nombre,
        descripcion=descripcion,
        momento=momento,
        orden=orden,
        frecuencia=frecuencia,
        dia_semana=dia_semana,
        dia_mes=dia_mes,
        fecha_inicio=fecha_inicio,
        requiere_foto=requiere_foto,
        checklist=list(checklist or []),
        asignado_a=asignado_a,
    )
    return TareaPlantillaRepo(session).add(plantilla)


def q_plantillas(session, empresa_id: uuid.UUID | None = None):
    return TareaPlantillaRepo(session).q_list(empresa_id)


def editar_plantilla(session, plantilla_id: uuid.UUID, **cambios) -> TareaPlantilla:
    plantilla = TareaPlantillaRepo(session).get(plantilla_id)
    if plantilla is None:
        raise NoEncontrado("plantilla no encontrada")
    for campo, valor in cambios.items():
        if valor is not None and hasattr(plantilla, campo):
            setattr(plantilla, campo, valor)
    session.flush()
    return plantilla


def desactivar_plantilla(session, plantilla_id: uuid.UUID) -> TareaPlantilla:
    """Desactivar, no borrar: las instancias ya generadas conservan su
    plantilla de origen para el historial del informe."""
    plantilla = TareaPlantillaRepo(session).get(plantilla_id)
    if plantilla is None:
        raise NoEncontrado("plantilla no encontrada")
    plantilla.activa = False
    session.flush()
    return plantilla
