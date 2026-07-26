"""Detección de conectividad hub → nube (ADR-009).

Solo aplica cuando `DEPLOYMENT_MODE=hub`. El hub decide por sí mismo si
tiene camino a la nube pingueando su `/health` (liveness, no toca
dependencias del lado nube — ver ADR-007); los clientes de la LAN nunca ven
esto, siempre le hablan al hub.

Estado en memoria del proceso, mismo patrón que `rate_limit.py`: un solo
proceso de hub por sucursal, no hace falta compartir estado entre workers.
"""

import logging
import time

import httpx

from src.config.settings import settings

log = logging.getLogger("provecho.sync")

EN_LINEA = "en_linea"
OFFLINE = "offline"

_TIMEOUT_SEGUNDOS = 3.0

_client = httpx.Client(timeout=_TIMEOUT_SEGUNDOS)

_estado = EN_LINEA
_fallos_consecutivos = 0
_ultima_conexion_ok: float | None = None


def _pingar() -> bool:
    try:
        respuesta = _client.get(f"{settings.cloud_sync_url.rstrip('/')}/health")
        respuesta.raise_for_status()
        return True
    except httpx.HTTPError:
        return False


def verificar_conectividad() -> dict:
    """Un ping. Actualiza y devuelve el estado — se llama en cada ciclo de
    sync y desde el endpoint de salud del hub."""
    global _estado, _fallos_consecutivos, _ultima_conexion_ok

    if _pingar():
        _fallos_consecutivos = 0
        _ultima_conexion_ok = time.monotonic()
        if _estado == OFFLINE:
            log.info("Hub reconectado a la nube")
        _estado = EN_LINEA
    else:
        _fallos_consecutivos += 1
        if _fallos_consecutivos >= settings.sync_fallos_para_offline and _estado == EN_LINEA:
            log.warning(
                "Hub sin conexión a la nube tras %s intentos", _fallos_consecutivos
            )
            _estado = OFFLINE

    return estado_actual()


def estado_actual() -> dict:
    segundos_desde_ok = (
        round(time.monotonic() - _ultima_conexion_ok, 1)
        if _ultima_conexion_ok is not None
        else None
    )
    return {
        "estado": _estado,
        "fallos_consecutivos": _fallos_consecutivos,
        "segundos_desde_ultima_conexion": segundos_desde_ok,
    }
