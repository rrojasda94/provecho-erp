"""Endpoints de salud. Públicos y sin autenticación —un monitor externo no
puede loguearse—, por eso devuelven estados y nunca detalles de
infraestructura: el detalle va al log.
"""

from fastapi import APIRouter, Response, status

from src.config.settings import settings
from src.core.health import CAIDO, revisar_backups, revisar_todo

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
