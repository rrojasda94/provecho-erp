"""Listener de `assets`: un requerimiento de activo recibido → el activo
nace solo.

Un solo evento hoy (`purchases.requerimiento_activo_recibido`), pero se
separa en su propio archivo desde el principio — mismo criterio que
`inventory`/`accounting`/`reports`: cuando `purchases` publique el evento
de OC de vehículo (deuda declarada) o cualquier otro origen empiece a dar
de alta activos, este es el lugar donde se suscribe, no una excepción al
patrón del resto del ERP.

El fallo de este listener **nunca** deshace la recepción de la OC —ya
commiteó, y el papeleo de compra es lo que de verdad importa—: si el
`id_interno` pedido ya lo usa otro activo (dos requerimientos con el mismo
código, o alguien ya lo dio de alta a mano mientras tanto), queda solo el
log; nadie más lo va a ver hasta que alguien revise el log de errores, así
que esa colisión —rarísima, dos personas tecleando el mismo código a la
vez— es deuda aceptada y no una tabla de incidencias nueva para un caso que
casi no ocurre.
"""

import logging
import uuid
from datetime import date
from decimal import Decimal

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.assets.application import activos as activos_uc
from src.modules.assets.application.errors import Conflicto

log = logging.getLogger("provecho.app")

# Inyectable (los tests la reemplazan) — mismo patrón que el resto del ERP.
session_factory = SessionLocal

_registrado = False


def on_requerimiento_activo_recibido(payload: dict) -> None:
    try:
        with session_factory() as session:
            activos_uc.crear_activo(
                session,
                empresa_id=uuid.UUID(payload["empresa_id"]),
                tipo="equipamiento",
                id_interno=payload["id_interno"],
                nombre=payload["nombre"],
                creado_por=uuid.UUID(payload["solicitado_por"]),
                sucursal_id=(
                    uuid.UUID(payload["sucursal_id"]) if payload.get("sucursal_id") else None
                ),
                categoria=payload.get("categoria"),
                marca=payload.get("marca"),
                modelo=payload.get("modelo"),
                fecha_compra=date.fromisoformat(payload["fecha_compra"]),
                valor_compra=Decimal(payload["costo_estimado"]),
                vida_util_meses=payload.get("vida_util_meses"),
                proveedor_id=uuid.UUID(payload["proveedor_id"]),
                responsable_trabajador_id=None,
            )
            session.commit()
    except Conflicto:
        log.exception(
            "no se pudo dar de alta el activo del requerimiento %s: id_interno duplicado",
            payload.get("requerimiento_activo_id"),
        )
    except Exception:
        log.exception(
            "fallo dando de alta el activo del requerimiento %s",
            payload.get("requerimiento_activo_id"),
        )


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("purchases.requerimiento_activo_recibido", on_requerimiento_activo_recibido)
