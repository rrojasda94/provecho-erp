"""Tareas de salud del propio worker.

Viven en `core` y no en un módulo de negocio: no reportan sobre el
restaurante sino sobre la infraestructura que lo atiende.
"""

from src.core.celery_app import celery_app
from src.core.health import registrar_latido_worker


@celery_app.task(name="core.latido_worker")
def latido_worker() -> bool:
    """Marca de vida del worker, para que `/health/ready` pueda preguntar en
    vez de inferir.

    Antes la salud del worker se deducía de la profundidad de la cola, que
    solo lo delata **cuando hay trabajo**: con la cola vacía, un worker
    muerto y uno ocioso se ven idénticos — y en un restaurante la cola está
    vacía la mayor parte del día, justo cuando conviene enterarse temprano.
    """
    registrar_latido_worker()
    return True
