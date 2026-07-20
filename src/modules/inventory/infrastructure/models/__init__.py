"""Modelos del módulo inventory — bloque transversal (data-model §1, §3)."""

from src.modules.inventory.infrastructure.models.categoria import Categoria
from src.modules.inventory.infrastructure.models.categoria_udm import CategoriaUdm
from src.modules.inventory.infrastructure.models.unidad_medida import UnidadMedida

__all__ = ["Categoria", "CategoriaUdm", "UnidadMedida"]
