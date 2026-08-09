"""Suscripción a los hechos del catálogo: un handler genérico por emisión.

No hay un `on_<evento>` escrito a mano por evento. Lo que cambia entre uno y
otro —título, nivel, ámbito, campos, a qué área va— está declarado en
`domain/catalogo.py`, así que agregar una emisión no toca este archivo. Antes
esto eran cuatro funciones casi idénticas en `users/application/listeners.py`,
y cada aviso nuevo era una quinta copia.

Cada handler abre **su propia sesión**: el bus despacha después del commit
del emisor (ADR-016), así que la transacción que originó el hecho ya cerró.
Un fallo acá no puede deshacerla, y por eso tampoco se propaga.
"""

import logging

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.reports.application import emision as emision_uc
from src.modules.reports.domain import catalogo

log = logging.getLogger("provecho.app")

# Inyectable: los tests la reemplazan (ver `MODULOS_CON_SESSION_FACTORY` en
# `tests/conftest.py`). Sin esto, cualquier test que confirme una venta o
# cierre una caja despertaría este listener contra el Postgres real.
session_factory = SessionLocal

_registrado = False


def _handler(codigo: str):
    def on_evento(payload: dict) -> None:
        try:
            with session_factory() as session:
                resultado = emision_uc.emitir(session, codigo, payload)
                if resultado is None:
                    return
                reporte, destinatarios = resultado
                if destinatarios:
                    # `users` lo consume y llena la bandeja. El salto extra
                    # existe para que `reports` no importe `notificacion`:
                    # el usuario tiene una sola campana y `users` sigue
                    # siendo su dueño.
                    event_bus.publish(
                        "reports.reporte_emitido",
                        {
                            "reporte_emitido_id": str(reporte.id),
                            "codigo": reporte.codigo_emision,
                            "titulo": reporte.titulo,
                            "cuerpo": reporte.cuerpo,
                            "nivel": reporte.nivel,
                            "sucursal_id": (
                                str(reporte.sucursal_id) if reporte.sucursal_id else None
                            ),
                            "referencia_tipo": reporte.referencia_tipo,
                            "referencia_id": (
                                str(reporte.referencia_id)
                                if reporte.referencia_id
                                else None
                            ),
                            "destinatarios": [str(u) for u in destinatarios],
                        },
                        session=session,
                    )
                session.commit()
        except Exception:
            # Un reporte que no se pudo emitir no puede tumbar la operación
            # que lo originó — ya está commiteada, de todos modos.
            log.exception("Falló la emisión de un reporte", extra={"codigo": codigo})

    on_evento.__name__ = f"on_{codigo.replace('.', '_')}"
    return on_evento


def register() -> None:
    """Idempotente: `create_app` puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    for emision in catalogo.CATALOGO:
        event_bus.subscribe(emision.codigo, _handler(emision.codigo))
