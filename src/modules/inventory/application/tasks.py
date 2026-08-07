"""Tareas en segundo plano de `inventory`: envío de la guía de remisión y
los dos barridos diarios del vencimiento.

Misma forma que `sales.tasks`: la tarea es una cáscara que abre la sesión,
delega en el caso de uso y decide si reintentar. La lógica vive en
`guias.py` / `lotes.py` / `conteos.py` y se prueba sin broker ni red.
"""

import uuid

from src.config.settings import settings
from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.modules.inventory.application import conteos, guias
from src.modules.inventory.application import lotes as lotes_uc
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


@celery_app.task(name="inventory.bloquear_lotes_vencidos")
def bloquear_lotes_vencidos() -> int:
    """Barrido diario de lotes vencidos con saldo disponible.

    El picking ya bloquea el lote vencido que se topa, pero solo cuando
    alguien lo toca: en un almacén de baja rotación el lote vencido queda
    contándose como disponible hasta que a alguien se le ocurre pedirlo.
    Corre **antes** del turno para que la primera salida del día no lo tome.

    Sin filtro de empresa ni de almacén: un periódico no tiene tenant, y un
    lote vencido lo está para todas.
    """
    session = SessionLocal()
    try:
        bloqueados = lotes_uc.bloquear_vencidos(session)
        session.commit()
        return len(bloqueados)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@celery_app.task(name="inventory.reportar_conteos_vencidos")
def reportar_conteos_vencidos() -> int:
    """Barrido diario de categorías que no se contaron en su fecha
    (RN-INV-021).

    Diario y no más seguido porque el dato cambia una vez por día: el
    calendario se deriva de fechas, no de horas. Que un conteo vencido se
    reporte todos los días hasta que se haga es deliberado —es un
    recordatorio, no una alerta de evento— a diferencia de
    `stock_bajo_minimo`, que avisa al cruzar justamente para no repetirse.
    """
    session = SessionLocal()
    try:
        vencidos = conteos.reportar_vencidos(session)
        session.commit()
        return len(vencidos)
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
