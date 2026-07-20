"""Modelos del módulo rrhh — alcance mínimo: `trabajador` (data-model §8b).

Este módulo se abre parcialmente como dependencia del slice Venta (ranking
de venta por trabajador). El resto de §8b (boleta_pago, memorandum,
amonestacion, acta, contrato_laboral, etc.) se modela en el slice
dedicado de RRHH.
"""

from src.modules.rrhh.infrastructure.models.trabajador import Trabajador

__all__ = ["Trabajador"]
