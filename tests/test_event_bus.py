from src.core.events import EventBus


def test_publish_reaches_all_subscribers() -> None:
    bus = EventBus()
    received: list[dict] = []
    bus.subscribe("sales.venta_confirmada", received.append)
    bus.subscribe("sales.venta_confirmada", received.append)

    bus.publish("sales.venta_confirmada", {"venta_id": "v1"})

    assert received == [{"venta_id": "v1"}, {"venta_id": "v1"}]


def test_publish_without_subscribers_is_noop() -> None:
    EventBus().publish("inventory.stock_bajo_minimo", {})
