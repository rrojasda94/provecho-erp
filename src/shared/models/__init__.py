"""Modelos transversales sin dueño de módulo (data-model, convenciones)."""

from src.shared.models.archivo import Archivo
from src.shared.models.comprobante import Comprobante
from src.shared.models.decision_gerencial import DecisionGerencial
from src.shared.models.divisa import Divisa
from src.shared.models.parametro_empresa import ParametroEmpresa

__all__ = [
    "Archivo",
    "Comprobante",
    "DecisionGerencial",
    "Divisa",
    "ParametroEmpresa",
]
