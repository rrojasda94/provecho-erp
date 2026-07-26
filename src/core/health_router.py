"""Endpoints de salud. Públicos y sin autenticación —un monitor externo no
puede loguearse—, por eso devuelven estados y nunca detalles de
infraestructura: el detalle va al log.
"""

from fastapi import APIRouter, Response, status

from src.config.settings import settings
from src.core.health import CAIDO, revisar_backups, revisar_todo
from src.core.sync import estado_conexion

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
    return {"aplica": True, **estado_conexion.verificar_conectividad()}
