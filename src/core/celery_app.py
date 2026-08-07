"""Cola de tareas en segundo plano (Celery sobre Redis).

Nació para la emisión de comprobantes electrónicos —la venta se cobra al
instante y el envío a SUNAT viaja aparte, con reintentos: una caída de
Factiliza nunca frena una caja— y hoy carga además los **barridos
periódicos** de `beat_schedule`, que son la red de seguridad de todo lo que
depende de que alguien mire a tiempo: pedidos demorados, lotes vencidos,
conteos vencidos y comprobantes que nunca llegaron a la cola.
"""

from celery import Celery
from celery.schedules import crontab
from celery.signals import celeryd_init

from src.config.settings import settings
from src.core.logging_config import configurar_logging
from src.core.sentry import iniciar_sentry

celery_app = Celery(
    "provecho",
    broker=settings.broker_url,
    backend=settings.broker_url,
    include=[
        "src.core.tasks_salud",
        "src.modules.inventory.application.tasks",
        "src.modules.sales.application.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Lima",
    enable_utc=True,
    # Encolar NUNCA puede colgar al que encola. Quien llama a `apply_async`
    # suele estar dentro de un request —el listener de `sales.venta_confirmada`
    # corre en la transacción que acaba de cobrar—, así que un broker caído
    # tiene que fallar en un segundo y no bloquear al cajero mirando una
    # pantalla congelada. El barrido periódico recupera lo que no se encoló.
    broker_connection_timeout=1.0,
    broker_connection_retry_on_startup=False,
    broker_transport_options={
        "socket_connect_timeout": 1,
        "socket_timeout": 1,
    },
)

# Barrido periódico de pedidos demorados (Celery beat).
#
# Cada venta confirmada ya agenda su propia revisión puntual; esto es la red
# de seguridad. Corre cada 5 minutos y no cada 15 porque no está sincronizado
# con ningún pedido en particular: con 5, una alerta que la tarea puntual
# perdió llega como mucho 5 minutos tarde.
#
# El barrido es idempotente (`UNIQUE (venta_id, minutos_umbral)`), así que
# solaparse con la revisión puntual no duplica nada. Levantarlo:
#   celery -A src.core.celery_app.celery_app beat
celery_app.conf.beat_schedule = {
    "barrer-pedidos-demorados": {
        "task": "sales.barrer_pedidos_demorados",
        "schedule": 300.0,
    },
    # Marca de vida del worker: `/health/ready` la lee en vez de deducir la
    # salud del worker por la profundidad de la cola, que con cola vacía no
    # distingue "muerto" de "ocioso". Cada minuto, con TTL de 3 min.
    "latido-worker": {
        "task": "core.latido_worker",
        "schedule": 60.0,
    },
    # Los dos barridos del vencimiento corren **antes del turno** y no a
    # cualquier hora: el vencimiento cambia al pasar la medianoche del
    # negocio (hora Perú, no UTC — `timezone` arriba), y bloquear el lote
    # recién a media mañana deja que la primera salida del día se lo lleve.
    "bloquear-lotes-vencidos": {
        "task": "inventory.bloquear_lotes_vencidos",
        "schedule": crontab(hour=6, minute=0),
    },
    "reportar-conteos-vencidos": {
        "task": "inventory.reportar_conteos_vencidos",
        "schedule": crontab(hour=6, minute=15),
    },
    # Red de seguridad de la emisión electrónica: recoge lo que nunca llegó
    # a la cola (emitido sin `FACTILIZA_TOKEN`, con el broker caído o con el
    # worker muerto). Cada 15 min alcanza — el reintento por comprobante ya
    # cubre la caída pasajera de Factiliza, y esto cubre la ausencia total.
    "barrer-comprobantes-pendientes": {
        "task": "sales.barrer_comprobantes_pendientes",
        "schedule": 900.0,
    },
}


@celeryd_init.connect
def _preparar_observabilidad(**_kwargs) -> None:
    """Solo en el proceso worker: la API importa este módulo únicamente para
    encolar y ya configuró lo suyo en `create_app`.

    Sin esto, un comprobante que agota sus reintentos contra Factiliza falla
    en silencio — nadie mira la salida del worker.
    """
    configurar_logging()
    iniciar_sentry("worker")
