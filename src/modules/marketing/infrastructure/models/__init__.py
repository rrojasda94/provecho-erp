"""Modelos del módulo marketing (data-model.md §8d)."""

from src.modules.marketing.infrastructure.models.campana import Campana
from src.modules.marketing.infrastructure.models.campana_metrica import CampanaMetrica
from src.modules.marketing.infrastructure.models.encuesta_plantilla import (
    EncuestaPlantilla,
)
from src.modules.marketing.infrastructure.models.encuesta_pregunta import (
    EncuestaPregunta,
)
from src.modules.marketing.infrastructure.models.encuesta_respuesta import (
    EncuestaRespuesta,
)
from src.modules.marketing.infrastructure.models.encuesta_satisfaccion import (
    EncuestaSatisfaccion,
)
from src.modules.marketing.infrastructure.models.evaluacion_agencia import (
    EvaluacionAgencia,
)
from src.modules.marketing.infrastructure.models.implementacion_material_sucursal import (
    ImplementacionMaterialSucursal,
)
from src.modules.marketing.infrastructure.models.lead import Lead
from src.modules.marketing.infrastructure.models.opcion_agencia import OpcionAgencia
from src.modules.marketing.infrastructure.models.pieza_contenido import PiezaContenido

__all__ = [
    "Campana",
    "CampanaMetrica",
    "EncuestaPlantilla",
    "EncuestaPregunta",
    "EncuestaRespuesta",
    "EncuestaSatisfaccion",
    "EvaluacionAgencia",
    "ImplementacionMaterialSucursal",
    "Lead",
    "OpcionAgencia",
    "PiezaContenido",
]
