"""Adaptador de Factiliza — facturación electrónica ante SUNAT (Perú)."""

from src.shared.integrations.factiliza.client import (
    ConsultaEmpresa,
    ConsultaPersona,
    FactilizaClient,
    FactilizaError,
    RespuestaEmision,
    nombres_desde_dni,
    razon_social_desde_ruc,
)
from src.shared.integrations.factiliza.mapper import (
    TIPO_DOC_BOLETA,
    TIPO_DOC_FACTURA,
    Cliente,
    Documento,
    Item,
    construir_payload,
    monto_en_letras,
)

__all__ = [
    "TIPO_DOC_BOLETA",
    "TIPO_DOC_FACTURA",
    "Cliente",
    "ConsultaEmpresa",
    "ConsultaPersona",
    "Documento",
    "FactilizaClient",
    "FactilizaError",
    "Item",
    "RespuestaEmision",
    "construir_payload",
    "monto_en_letras",
    "nombres_desde_dni",
    "razon_social_desde_ruc",
]
