from collections import defaultdict
from collections.abc import Callable
from typing import Any

Handler = Callable[[dict[str, Any]], None]


class EventBus:
    """Bus de eventos interno: única vía de comunicación entre módulos.

    Síncrono y en proceso. Convención de nombres: "<modulo>.<evento_en_pasado>",
    ej. "sales.venta_confirmada".
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._handlers[event_name].append(handler)

    def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        for handler in self._handlers[event_name]:
            handler(payload)


event_bus = EventBus()
