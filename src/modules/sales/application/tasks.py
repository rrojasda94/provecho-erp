"""Tareas en segundo plano de `sales`: envío del comprobante a Factiliza.

La tarea es una cáscara — abre la sesión, delega en el caso de uso y
decide si reintentar. La lógica vive en `comprobantes.py`, que se prueba
sin broker ni red.
"""

import uuid

from src.config.settings import settings
from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.modules.sales.application import alertas, comprobantes
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
    corre en otro proceso y solo ve filas ya confirmadas.

    En un hub de sucursal no hace nada: no corre Celery ni Redis y la
    emisión a SUNAT es siempre de la nube, después del sync (ADR-009). Sin
    esta guarda, cobrar durante un corte intentaría hablarle a un broker
    inexistente.
    """
    if settings.es_hub or not comprobantes.emision_habilitada():
        return
    emitir_comprobante.delay(str(comprobante_id))


# --- Alerta de pedido demorado ----------------------------------------------
@celery_app.task(name="sales.revisar_demora_pedido")
def revisar_demora_pedido(venta_id: str) -> bool:
    """Revisión puntual: ¿este pedido sigue en cocina pasado el umbral?

    Devuelve si se creó la alerta. Sin reintentos a propósito: si falla, el
    barrido periódico lo vuelve a mirar en el próximo ciclo — reintentar
    acá solo adelantaría lo que la red de seguridad ya hace.
    """
    session = SessionLocal()
    try:
        alerta = alertas.revisar_pedido(session, uuid.UUID(venta_id))
        session.commit()
        return alerta is not None
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@celery_app.task(name="sales.barrer_comprobantes_pendientes")
def barrer_comprobantes_pendientes() -> int:
    """Reencola los comprobantes que nunca llegaron a la cola.

    No emite acá: encola uno por comprobante para que cada uno conserve su
    propio backoff y su cuenta de intentos. Un barrido que emitiera en línea
    convertiría una caída de Factiliza en un ciclo de 100 timeouts.
    """
    if not comprobantes.emision_habilitada():
        return 0
    session = SessionLocal()
    try:
        ids = comprobantes.pendientes_de_emitir(session)
    finally:
        session.close()
    for comprobante_id in ids:
        emitir_comprobante.apply_async(args=[str(comprobante_id)], retry=False)
    return len(ids)


@celery_app.task(name="sales.barrer_pedidos_demorados")
def barrer_pedidos_demorados() -> int:
    """Barrido periódico (Celery beat). Red de seguridad de la revisión
    puntual: levanta lo que se perdió porque el worker estaba caído, el
    broker soltó la tarea, o la venta nació sin worker escuchando."""
    session = SessionLocal()
    try:
        creadas = alertas.barrer(session)
        session.commit()
        return len(creadas)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def programar_revision_demora(venta_id: str) -> None:
    """Agenda la revisión para dentro del umbral, desde el listener de
    `sales.venta_confirmada`.

    El `countdown` usa el umbral por defecto y no el de la empresa: leerlo
    exigiría una sesión dentro del listener, y de todos modos la tarea
    revalida el umbral real al ejecutarse. Si Gerencia lo subió, la
    revisión puntual simplemente no encuentra nada y el barrido alerta
    cuando corresponde.

    En un hub de sucursal no hace nada — no corre Celery (ADR-009).

    **`retry=False` no es un detalle.** Por defecto `apply_async` reintenta
    la conexión al broker *dentro* de la llamada, con backoff: si Redis está
    caído, el request que confirmó la venta se queda esperando ahí y el
    cajero mira una pantalla colgada. Como esto corre en el listener de
    `sales.venta_confirmada`, o falla al instante o no vale la pena — y si
    falla, el barrido periódico levanta el pedido igual.
    """
    if settings.es_hub:
        return
    revisar_demora_pedido.apply_async(
        args=[venta_id],
        countdown=alertas.UMBRAL_DEFECTO_MINUTOS * 60,
        retry=False,
    )
