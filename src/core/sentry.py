"""Reporte de errores a Sentry (o GlitchTip, que habla el mismo protocolo).

Sin `SENTRY_DSN` no hace nada: en local y en tests no se envía un solo byte.
Todo lo que sale de acá pasa antes por el redactor de datos sensibles — un
reporte de error es el lugar más fácil para filtrar un PIN sin querer.
"""

import logging

from src.config.settings import settings
from src.core.logging_config import CLAVES_SENSIBLES, REDACTADO, redactar

log = logging.getLogger(__name__)
_iniciado = False


def _limpiar_evento(evento: dict, _hint: dict) -> dict | None:
    evento = redactar(evento)
    cabeceras = evento.get("request", {}).get("headers")
    if isinstance(cabeceras, dict):
        for nombre in list(cabeceras):
            if nombre.lower() in CLAVES_SENSIBLES or nombre.lower() == "cookie":
                cabeceras[nombre] = REDACTADO
    return evento


def iniciar_sentry(componente: str) -> bool:
    """Arranca el reporte de errores para `componente` (api|worker|backups).

    Devuelve False si no hay DSN configurado — el caso normal fuera de
    producción. Idempotente.
    """
    global _iniciado
    if _iniciado:
        return True
    if not settings.sentry_dsn:
        return False

    try:
        import sentry_sdk
    except ImportError:
        log.warning("SENTRY_DSN configurado pero sentry-sdk no está instalado")
        return False

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=settings.app_version,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        # El ERP maneja datos de trabajadores y clientes (Ley 29733):
        # nunca se adjunta el cuerpo del request ni la IP del usuario.
        send_default_pii=False,
        before_send=_limpiar_evento,
    )
    sentry_sdk.set_tag("componente", componente)
    _iniciado = True
    log.info("Reporte de errores activo (%s)", componente)
    return True


def reportar(excepcion: BaseException) -> None:
    """Envía una excepción ya capturada. No-op sin Sentry configurado."""
    if not _iniciado:
        return
    import sentry_sdk

    sentry_sdk.capture_exception(excepcion)
