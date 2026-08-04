"""Reglas de negocio de autenticación y autorización (users).

Invariantes puras, sin dependencias de infraestructura.
"""

import re
from dataclasses import dataclass
from datetime import time, timedelta
from decimal import Decimal

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


# --- Restricciones de permiso (ADR-022) --------------------------------------
@dataclass(frozen=True)
class ContextoPermiso:
    """Datos reales de la operación contra los que se evalúa
    `permiso.restricciones`. Ninguno es obligatorio: una dimensión sin dato
    en el contexto no bloquea — el llamador decide qué exige pasando o no
    ese campo (ej. un permiso con `horario` pero un caller que nunca pasa
    `hora` nunca lo acota, a propósito: no todo permiso con restricción de
    horario aplica en todos los flujos que lo usan)."""

    monto: Decimal | None = None
    estado: str | None = None
    hora: time | None = None


def cumple_restricciones(restricciones: dict | None, contexto: ContextoPermiso) -> bool:
    """Evalúa `permiso.restricciones` (JSONB) contra `contexto`. Sin
    restricciones, siempre cumple. Claves soportadas: `monto_maximo`,
    `estados_permitidos` (lista), `horario` ({"desde": "HH:MM", "hasta":
    "HH:MM"})."""
    if not restricciones:
        return True
    monto_maximo = restricciones.get("monto_maximo")
    if monto_maximo is not None and contexto.monto is not None:
        if contexto.monto > Decimal(str(monto_maximo)):
            return False
    estados_permitidos = restricciones.get("estados_permitidos")
    if estados_permitidos and contexto.estado is not None:
        if contexto.estado not in estados_permitidos:
            return False
    horario = restricciones.get("horario")
    if horario and contexto.hora is not None:
        desde = time.fromisoformat(horario["desde"])
        hasta = time.fromisoformat(horario["hasta"])
        if not (desde <= contexto.hora <= hasta):
            return False
    return True
