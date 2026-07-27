"""Chequeos de salud de las dependencias del ERP.

El ERP no manda alertas por su cuenta: expone su estado y deja que un
monitor externo (healthchecks.io, UptimeRobot, Uptime Kuma) haga el aviso.
Construir un sistema de alertas propio sería reinventar algo que además
falla justo cuando el servidor se cae — el monitor tiene que vivir afuera.

Ninguna respuesta incluye hostnames, DSN ni mensajes de error crudos: el
detalle va al log, no al endpoint, que es público.
"""

import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import redis
from sqlalchemy import text

from src.config.settings import settings
from src.core.database import engine

log = logging.getLogger("provecho.app")

OK = "ok"
DEGRADADO = "degradado"
CAIDO = "caido"

# La cola de comprobantes se vacía sola; que crezca significa que el worker
# murió o que Factiliza lleva rato rechazando.
COLA_CELERY = "celery"


def _resultado(estado: str, **extra) -> dict:
    return {"estado": estado, **extra}


def revisar_base_datos() -> dict:
    """Crítico: sin base de datos el ERP no puede atender nada."""
    inicio = time.perf_counter()
    try:
        with engine.connect() as conexion:
            conexion.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001 — cualquier fallo es "no disponible"
        log.error("Chequeo de base de datos falló: %s", e)
        return _resultado(CAIDO)
    return _resultado(OK, latencia_ms=round((time.perf_counter() - inicio) * 1000, 1))


def _cliente_redis() -> redis.Redis:
    return redis.from_url(
        settings.redis_url, socket_timeout=0.5, socket_connect_timeout=0.5
    )


def revisar_redis() -> dict:
    """No crítico: sin Redis el rate limit falla abierto y la emisión de
    comprobantes se posterga, pero la caja sigue vendiendo."""
    try:
        _cliente_redis().ping()
    except redis.RedisError as e:
        log.warning("Chequeo de Redis falló: %s", e)
        return _resultado(DEGRADADO)
    return _resultado(OK)


def revisar_cola() -> dict:
    """Profundidad de la cola de tareas. Una cola que crece y no baja
    significa worker muerto, no tráfico alto."""
    try:
        pendientes = _cliente_redis().llen(COLA_CELERY)
    except redis.RedisError:
        return _resultado(DEGRADADO)
    estado = DEGRADADO if pendientes > settings.health_cola_maxima else OK
    if estado == DEGRADADO:
        log.warning("Cola de tareas con %s pendientes", pendientes)
    return _resultado(estado, pendientes=pendientes)


def revisar_backups(ahora: datetime | None = None) -> dict:
    """El caso traicionero no es el backup que falla —ese ya reporta a
    Sentry— sino el que **nunca corrió**: cron desactivado, servidor
    reinstalado, nadie se entera hasta que hace falta restaurar."""
    ahora = ahora or datetime.now(UTC)
    directorio = Path(settings.backup_dir)
    archivos = list(directorio.glob("provecho-*.dump")) if directorio.is_dir() else []
    if not archivos:
        log.warning("No hay ningún backup en %s", directorio)
        return _resultado(CAIDO, motivo="sin_backups")
    ultimo = max(archivos, key=lambda p: p.stat().st_mtime)
    horas = (ahora - datetime.fromtimestamp(ultimo.stat().st_mtime, UTC)).total_seconds() / 3600
    if horas > settings.health_backup_max_horas:
        log.warning("El último backup tiene %.1f horas", horas)
        return _resultado(CAIDO, horas_desde_ultimo=round(horas, 1))
    return _resultado(OK, horas_desde_ultimo=round(horas, 1))


def estado_general(componentes: dict[str, dict]) -> str:
    estados = {c["estado"] for c in componentes.values()}
    if CAIDO in estados:
        return CAIDO
    return DEGRADADO if DEGRADADO in estados else OK


def revisar_todo() -> tuple[str, dict]:
    """Readiness: ¿puede este proceso atender tráfico?

    Los backups no entran acá a propósito — que falte un backup es grave,
    pero sacar la API de rotación por eso dejaría al restaurante sin vender.
    Se expone aparte, para que el monitor lo alerte sin tumbar nada.
    """
    componentes = {
        "base_datos": revisar_base_datos(),
        "redis": revisar_redis(),
        "cola": revisar_cola(),
    }
    return estado_general(componentes), componentes
