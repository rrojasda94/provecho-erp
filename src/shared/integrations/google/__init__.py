"""Adaptador de Google — distancia de reparto (Routes API).

El autocompletado y el mapa NO pasan por acá: los habla el navegador con su
propia clave, porque el widget oficial de Places maneja los tokens de sesión
que abaratan la factura y reimplementarlo server-side costaría más y cobraría
más (ADR-053). Lo que sí vive en el servidor es lo que define cuánta plata
paga el cliente (ADR-054).
"""

from src.shared.integrations.google.rutas import (
    Coordenada,
    RutasError,
    distancia_km,
    habilitado,
)

__all__ = ["Coordenada", "RutasError", "distancia_km", "habilitado"]
