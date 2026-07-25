"""Reglas de negocio de autenticación y autorización (users).

Invariantes puras, sin dependencias de infraestructura.
"""

import re
from datetime import timedelta

PIN_LENGTH = 6
_PIN_RE = re.compile(rf"^\d{{{PIN_LENGTH}}}$")

# Lockout: N intentos fallidos bloquean el login por una ventana.
MAX_INTENTOS_FALLIDOS = 5
DURACION_BLOQUEO = timedelta(minutes=15)

# Comodín de permiso total (solo rol admin en entornos internos).
PERMISO_TODO = "*"


def pin_valido(pin: str) -> bool:
    """PIN = exactamente PIN_LENGTH dígitos."""
    return bool(_PIN_RE.match(pin))


def permite(codigos_permiso: set[str], accion: str) -> bool:
    """Deny por defecto: la acción se permite solo si hay permiso explícito
    o el comodín total."""
    return PERMISO_TODO in codigos_permiso or accion in codigos_permiso
