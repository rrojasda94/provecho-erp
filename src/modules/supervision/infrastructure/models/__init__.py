"""Modelos del módulo supervision (data-model.md, sección Supervisión)."""

from src.modules.supervision.infrastructure.models.categoria_tarea import CategoriaTarea
from src.modules.supervision.infrastructure.models.informe_diario import InformeDiario
from src.modules.supervision.infrastructure.models.tarea_instancia import TareaInstancia
from src.modules.supervision.infrastructure.models.tarea_plantilla import TareaPlantilla

__all__ = ["CategoriaTarea", "InformeDiario", "TareaInstancia", "TareaPlantilla"]
