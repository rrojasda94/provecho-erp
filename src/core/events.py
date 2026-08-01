"""Bus de eventos interno: única vía de comunicación entre módulos.

Síncrono y en proceso. Convención de nombres: "<modulo>.<evento_en_pasado>",
ej. "sales.venta_confirmada".

**El evento se despacha recién cuando commitea la sesión que lo publicó.**
Un caso de uso publica en medio de su transacción, cuando todavía puede
fallar: el `UNIQUE (sucursal, fecha, numero_orden)` de una venta salta en el
`commit()` del router, no antes. Despachar en ese momento dejaba a los
listeners —que abren su propia sesión y commitean por separado— descontando
stock de una venta que nunca existió. Bufferizando en `session.info` y
vaciando en `after_commit` desaparece esa ventana, y de paso el listener ya
puede *leer* lo que publicó el emisor.

Pasar `session=` es lo normal; omitirlo despacha en el acto y solo tiene
sentido fuera de una transacción.
"""

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], None]

# Clave del buffer dentro de `Session.info` (dict libre por sesión).
_PENDIENTES = "provecho.eventos_pendientes"


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._handlers[event_name].append(handler)

    def publish(
        self,
        event_name: str,
        payload: dict[str, Any],
        *,
        session: Session | None = None,
    ) -> None:
        if session is None:
            self._despachar(event_name, payload)
            return
        session.info.setdefault(_PENDIENTES, []).append((event_name, payload))

    def despachar_pendientes(self, session: Session) -> None:
        for event_name, payload in session.info.pop(_PENDIENTES, []):
            self._despachar(event_name, payload)

    def descartar_pendientes(self, session: Session) -> None:
        session.info.pop(_PENDIENTES, None)

    def _despachar(self, event_name: str, payload: dict[str, Any]) -> None:
        for handler in self._handlers[event_name]:
            try:
                handler(payload)
            except Exception:
                # Post-commit ya no hay nada que deshacer: propagar solo
                # rompería al emisor por un fallo ajeno. Es el criterio que
                # los listeners ya aplicaban por su cuenta (un fallo de
                # inventario nunca cancela la venta); acá vale para todos.
                log.exception("handler de %s falló", event_name)


event_bus = EventBus()


@sa_event.listens_for(Session, "after_commit")
def _despachar_al_commitear(session: Session) -> None:
    event_bus.despachar_pendientes(session)


@sa_event.listens_for(Session, "after_soft_rollback")
def _descartar_al_revertir(session: Session, previous_transaction: Any) -> None:
    # También en el rollback de un SAVEPOINT: soltar un evento cuyos datos
    # quizá se deshicieron es peor que perderlo.
    event_bus.descartar_pendientes(session)
