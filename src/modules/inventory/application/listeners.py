"""Listeners de eventos de otros módulos → movimientos de inventario.

`sales.venta_confirmada` descuenta insumos según receta (+ merma % +
empaque por modalidad); `sales.venta_anulada` repone. La comunicación es
solo vía event bus — nunca imports del dominio de sales.

Un fallo de inventario NUNCA rompe la venta: el handler atrapa y loguea.
"""

import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.inventory.application import stock as stock_uc
from src.modules.inventory.application.errors import StockInsuficiente
from src.modules.inventory.infrastructure.models import RecetaItem, Sku

# Almacén/Sucursal son organización transversal (data-model §1); viven en
# users/infrastructure por historia. Import de modelo (no dominio) permitido.
from src.modules.users.infrastructure.models import Almacen

log = logging.getLogger(__name__)

# Inyectable (tests la reemplazan). ponytail: el listener commitea su propia
# sesión — si el commit de la venta fallara post-flush, la discrepancia la
# detecta el conteo; patrón outbox cuando llegue Celery.
session_factory = SessionLocal


def _almacen_de_sucursal(session: Session, sucursal_id: uuid.UUID) -> uuid.UUID | None:
    return session.scalar(
        select(Almacen.id).where(
            Almacen.sucursal_id == sucursal_id, Almacen.deleted_at.is_(None)
        )
    )


def _sku_de_articulo(session: Session, articulo_id: uuid.UUID) -> uuid.UUID | None:
    # ponytail: SKU activo de mayor prioridad; elección por lote llega con FEFO.
    return session.scalar(
        select(Sku.id)
        .where(Sku.articulo_id == articulo_id, Sku.activo.is_(True))
        .order_by(Sku.prioridad)
    )


def _consumos_de_items(session: Session, items: list[dict]) -> list[tuple[uuid.UUID, Decimal]]:
    """Expande items de venta → [(articulo_id, cantidad_a_consumir)]."""
    consumos: list[tuple[uuid.UUID, Decimal]] = []
    for it in items:
        cantidad_vendida = Decimal(it["cantidad"])
        for ri in session.scalars(
            select(RecetaItem).where(RecetaItem.receta_id == uuid.UUID(it["receta_id"]))
        ):
            # Consumo = cantidad de receta × vendido × (1 + merma%).
            consumo = (
                ri.cantidad * cantidad_vendida * (1 + ri.merma_pct / 100)
            )
            consumos.append((ri.articulo_id, consumo))
        if it.get("empaque_articulo_id"):
            consumos.append(
                (uuid.UUID(it["empaque_articulo_id"]), cantidad_vendida)
            )
    return consumos


def _mover(payload: dict, tipo: str, signo: int) -> None:
    # Un solo exit con commit SIEMPRE: un return temprano cerraría la sesión
    # con rollback, y con conexión compartida (SQLite en tests) ese rollback
    # arrastraría la transacción del request que publicó el evento.
    movio = False
    with session_factory() as session:
        almacen_id = _almacen_de_sucursal(
            session, uuid.UUID(payload["sucursal_id"])
        )
        if almacen_id is None:
            log.warning(
                "venta %s: sucursal sin almacén, consumo omitido",
                payload["venta_id"],
            )
        else:
            for articulo_id, cantidad in _consumos_de_items(session, payload["items"]):
                sku_id = _sku_de_articulo(session, articulo_id)
                if sku_id is None:
                    log.warning(
                        "venta %s: artículo %s sin SKU activo, ítem omitido",
                        payload["venta_id"], articulo_id,
                    )
                    continue
                try:
                    stock_uc.registrar_movimiento(
                        session,
                        almacen_id=almacen_id,
                        sku_id=sku_id,
                        cantidad=cantidad * signo,
                        tipo=tipo,
                        referencia=payload["venta_id"],
                    )
                    movio = True
                except StockInsuficiente:
                    # ponytail: la venta ya ocurrió — el stock teórico no la
                    # bloquea; queda la discrepancia para conteo/ajuste.
                    log.warning(
                        "venta %s: stock insuficiente de sku %s, consumo omitido",
                        payload["venta_id"], sku_id,
                    )
        session.commit()
    if movio:
        event_bus.publish(
            "inventory.stock_consumido"
            if signo < 0
            else "inventory.stock_repuesto",
            {"venta_id": payload["venta_id"]},
        )


def on_venta_confirmada(payload: dict) -> None:
    try:
        _mover(payload, tipo="consumo_venta", signo=-1)
    except Exception:
        log.exception("fallo consumiendo stock de venta %s", payload.get("venta_id"))


def on_venta_anulada(payload: dict) -> None:
    try:
        _mover(payload, tipo="devolucion", signo=+1)
    except Exception:
        log.exception("fallo reponiendo stock de venta %s", payload.get("venta_id"))


_registrado = False


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("sales.venta_confirmada", on_venta_confirmada)
    event_bus.subscribe("sales.venta_anulada", on_venta_anulada)
