"""Tareas en segundo plano de `sales`: envío del comprobante a Factiliza.

La tarea es una cáscara — abre la sesión, delega en el caso de uso y
decide si reintentar. La lógica vive en `comprobantes.py`, que se prueba
sin broker ni red.
"""

import uuid

from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.modules.sales.application import comprobantes
from src.shared.integrations.factiliza import FactilizaError

# Reintentos espaciados: 1, 2, 4... minutos. Un rechazo de SUNAT no
# reintenta (no es fallo de transporte, el dato está mal).
REINTENTOS_MAXIMOS = 4
ESPERA_BASE_SEGUNDOS = 60


@celery_app.task(
    bind=True,
    name="sales.emitir_comprobante",
    autoretry_for=(FactilizaError,),
    retry_backoff=ESPERA_BASE_SEGUNDOS,
    retry_kwargs={"max_retries": REINTENTOS_MAXIMOS},
)
def emitir_comprobante(self, comprobante_id: str) -> str:
    session = SessionLocal()
    try:
        comprobante = comprobantes.emitir_comprobante(
            session, uuid.UUID(comprobante_id)
        )
        session.commit()
        return comprobante.estado_emision
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


def encolar(comprobante_id: uuid.UUID) -> None:
    """Encola el envío. Se llama DESPUÉS del commit de la venta: el worker
    corre en otro proceso y solo ve filas ya confirmadas."""
    if not comprobantes.emision_habilitada():
        return
    emitir_comprobante.delay(str(comprobante_id))
