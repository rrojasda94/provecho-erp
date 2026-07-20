"""Modelos del módulo users: persona y organización (data-model §1, §2)."""

from src.modules.users.infrastructure.models.almacen import Almacen
from src.modules.users.infrastructure.models.empresa import Empresa
from src.modules.users.infrastructure.models.grupo import Grupo
from src.modules.users.infrastructure.models.licencia_marca import LicenciaMarca
from src.modules.users.infrastructure.models.marca import Marca
from src.modules.users.infrastructure.models.persona import Persona
from src.modules.users.infrastructure.models.sucursal import Sucursal

__all__ = [
    "Almacen",
    "Empresa",
    "Grupo",
    "LicenciaMarca",
    "Marca",
    "Persona",
    "Sucursal",
]
