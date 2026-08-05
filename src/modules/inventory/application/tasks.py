"""Tareas en segundo plano de `inventory`: envío de la guía de remisión.

Misma forma que `sales.tasks`: la tarea es una cáscara que abre la sesión,
delega en el caso de uso y decide si reintentar. La lógica vive en
`guias.py` y se prueba sin broker ni red.
"""

import uuid

from src.config.settings import settings
from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.modules.inventory.application import guias
from src.shared.integrations.factiliza import FactilizaError

REINTENTOS_MAXIMOS = 4
ESPERA_BASE_SEGUNDOS = 60


@celery_app.task(
    bind=True,
    name="inventory.emitir_guia_remision",
    autoretry_for=(FactilizaError,),
    retry_backoff=ESPERA_BASE_SEGUNDOS,
    retry_kwargs={"max_retries": REINTENTOS_MAXIMOS},
)
def emitir_guia_remision(self, guia_id: str) -> str:
    session = SessionLocal()
    try:
        guia = guias.enviar_a_sunat(session, uuid.UUID(guia_id))
        session.commit()
        return guia.estado_emision
    except FactilizaError:
        # El intento quedó contado en la fila; persistirlo evita reintentar
        # para siempre contra un proveedor caído.
        session.commit()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def encolar(guia_id: uuid.UUID) -> None:
    """Encola el envío DESPUÉS del commit: el worker corre en otro proceso y
    solo ve filas ya confirmadas.

    `retry=False` por el mismo motivo que en `sales`: quien llama está
    dentro del request que acaba de emitir la guía, y con el broker caído
    `apply_async` se quedaría reintentando la conexión con el almacenero
    mirando una pantalla colgada. La guía impresa es la que viaja; el envío
    a SUNAT puede esperar al próximo intento.
    """
    if settings.es_hub or not settings.factiliza_token:
        return
    emitir_guia_remision.apply_async(args=[str(guia_id)], retry=False)
