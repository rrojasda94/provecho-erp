"""Cola de tareas en segundo plano (Celery sobre Redis).

Hoy solo la usa la emisión de comprobantes electrónicos: la venta se cobra
al instante y el envío a SUNAT viaja aparte, con reintentos — una caída de
Factiliza nunca frena una caja.
"""

from celery import Celery
from celery.signals import celeryd_init

from src.config.settings import settings
from src.core.logging_config import configurar_logging
from src.core.sentry import iniciar_sentry

celery_app = Celery(
    "provecho",
    broker=settings.broker_url,
    backend=settings.broker_url,
    include=["src.modules.sales.application.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Lima",
    enable_utc=True,
)


@celeryd_init.connect
def _preparar_observabilidad(**_kwargs) -> None:
    """Solo en el proceso worker: la API importa este módulo únicamente para
    encolar y ya configuró lo suyo en `create_app`.

    Sin esto, un comprobante que agota sus reintentos contra Factiliza falla
    en silencio — nadie mira la salida del worker.
    """
    configurar_logging()
    iniciar_sentry("worker")
