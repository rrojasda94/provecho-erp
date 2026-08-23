"""Endpoints de salud. Públicos y sin autenticación —un monitor externo no
puede loguearse—, por eso devuelven estados y nunca detalles de
infraestructura: el detalle va al log.
"""

import logging

from fastapi import APIRouter, Response, status
from sqlalchemy.exc import SQLAlchemyError

from src.config.settings import settings
from src.core.database import SessionLocal
from src.core.health import CAIDO, revisar_backups, revisar_todo
from src.core.sync import estado_conexion, watermark

log = logging.getLogger("provecho.sync")

router = APIRouter(tags=["core"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: ¿el proceso responde? No toca dependencias — si fallara por
    la base de datos, el orquestador reiniciaría en bucle un proceso sano."""
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@router.get("/health/ready")
def health_ready(respuesta: Response) -> dict:
    """Readiness: ¿puede atender tráfico? 503 si una dependencia crítica
    cayó, para que el monitor externo alerte y el proxy lo saque de rotación."""
    estado, componentes = revisar_todo()
    if estado == CAIDO:
        respuesta.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": estado, "componentes": componentes}


@router.get("/health/backups")
def health_backups(respuesta: Response) -> dict:
    """Frescura del último backup, aparte del readiness: que falte un backup
    es grave, pero sacar la API de rotación por eso dejaría al restaurante
    sin vender."""
    resultado = revisar_backups()
    if resultado["estado"] == CAIDO:
        respuesta.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return resultado


# HEAD aparte y fuera del schema, no vía el auto-agregado de Starlette/
# FastAPI a `@router.get(...)`: dejó de funcionar en la versión instalada
# (descubierto 2026-08-23, monitor UptimeRobot en plan gratis, que sondea
# con HEAD y no permite cambiar a GET). `include_in_schema=False` porque
# HEAD es implícito en HTTP para cualquier GET — documentarlo aparte solo
# duplicaría el operation ID en el contrato OpenAPI.
for _ruta, _vista in (
    ("/health", health),
    ("/health/ready", health_ready),
    ("/health/backups", health_backups),
):
    router.add_api_route(_ruta, _vista, methods=["HEAD"], include_in_schema=False)


@router.get("/health/sync")
def health_sync() -> dict:
    """Solo tiene sentido en un hub (ADR-009): si este proceso es la nube,
    lo dice explícitamente en vez de fingir un estado que no aplica.

    Siempre 200: a diferencia de `/health/ready`, "offline" acá NO significa
    que el hub esté fallando — es justo su modo de diseño durante un corte
    de internet, y sigue sirviendo perfecto a la LAN. Sacarlo de rotación
    por esto sería exactamente lo contrario de lo que se necesita. Es
    diagnóstico para que un monitor externo avise si lleva offline
    demasiado tiempo, no una señal de "no sirvas tráfico".
    """
    if not settings.es_hub:
        return {"aplica": False, "motivo": "deployment_mode=cloud"}
    return {
        "aplica": True,
        **estado_conexion.verificar_conectividad(),
        # Hasta dónde llegó el motor, por recurso: el ping dice si hay
        # internet, esto dice si el sync realmente está avanzando. Corre en
        # el proceso de la API, así que se lee de la base y no de memoria —
        # el runner es otro proceso.
        "recursos": _watermarks(),
    }


def _watermarks() -> list[dict] | None:
    """None (y no 503) si la base no responde: `/health/ready` ya cubre eso
    y este endpoint no debe fallar por un diagnóstico."""
    try:
        with SessionLocal() as session:
            return watermark.resumen(session)
    except SQLAlchemyError:
        log.warning("No se pudo leer el estado de sync", exc_info=True)
        return None
