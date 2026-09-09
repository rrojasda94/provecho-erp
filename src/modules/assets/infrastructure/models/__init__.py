"""Modelos del módulo assets: activo, vehículo, mantenimiento y vigencias
(data-model.md §Recursos)."""

from src.modules.assets.infrastructure.models.activo import Activo
from src.modules.assets.infrastructure.models.carga_combustible import (
    CargaCombustible,
)
from src.modules.assets.infrastructure.models.documento_vigencia import (
    DocumentoVigencia,
)
from src.modules.assets.infrastructure.models.lectura_odometro import (
    LecturaOdometro,
)
from src.modules.assets.infrastructure.models.orden_mantenimiento import (
    OrdenMantenimiento,
)
from src.modules.assets.infrastructure.models.orden_mantenimiento_repuesto import (
    OrdenMantenimientoRepuesto,
)
from src.modules.assets.infrastructure.models.plan_mantenimiento import (
    PlanMantenimiento,
)
from src.modules.assets.infrastructure.models.repuesto_compatibilidad import (
    RepuestoCompatibilidad,
)
from src.modules.assets.infrastructure.models.vehiculo import Vehiculo

__all__ = [
    "Activo",
    "CargaCombustible",
    "DocumentoVigencia",
    "LecturaOdometro",
    "OrdenMantenimiento",
    "OrdenMantenimientoRepuesto",
    "PlanMantenimiento",
    "RepuestoCompatibilidad",
    "Vehiculo",
]
