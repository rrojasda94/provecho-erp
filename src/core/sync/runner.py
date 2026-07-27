"""Proceso de sincronización del hub (ADR-009, fase 2).

Un bucle simple en su propio contenedor, no Celery: el hub corre en un
Raspberry Pi y montar broker + worker para una tarea periódica cada minuto
sería más infraestructura que trabajo. Si el proceso muere, Docker lo
reinicia y el watermark en base retoma donde quedó.

Uso:
    python -m src.core.sync.runner
"""

import logging
import signal
import sys
import time
from types import FrameType

from src.config.settings import settings
from src.core.logging_config import configurar_logging
from src.core.sentry import iniciar_sentry
from src.core.sync import motor

log = logging.getLogger("provecho.sync")

_corriendo = True


def _detener(signo: int, marco: FrameType | None) -> None:
    """SIGTERM de `docker stop`: terminar el ciclo en curso y salir limpio,
    en vez de morir a mitad de un lote."""
    global _corriendo
    _corriendo = False
    log.info("Señal %s recibida; el runner de sync termina tras este ciclo", signo)


def main() -> int:
    configurar_logging()
    iniciar_sentry("sync")
    if not settings.es_hub:
        log.error("El runner de sync solo corre con DEPLOYMENT_MODE=hub")
        return 1

    signal.signal(signal.SIGTERM, _detener)
    signal.signal(signal.SIGINT, _detener)
    log.info(
        "Runner de sync iniciado (sucursal %s, cada %ss)",
        settings.hub_sucursal_id,
        settings.sync_intervalo_segundos,
    )
    while _corriendo:
        try:
            resumen = motor.ciclo()
            log.debug("ciclo de sync: %s", resumen)
        except Exception:
            # Nada tumba el runner: el local sigue vendiendo aunque el sync
            # esté roto, y el próximo ciclo vuelve a intentar.
            log.exception("Fallo no controlado en el ciclo de sync")
        for _ in range(settings.sync_intervalo_segundos):
            if not _corriendo:
                break
            time.sleep(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
