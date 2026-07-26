"""Casos de uso de stock: consulta y registro de movimientos.

El stock nunca se edita directo — todo cambio pasa por
`movimiento_inventario`, que aquí se inserta y refleja en la fila `stock`.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.inventory.application.errors import ReglaNegocio, StockInsuficiente
from src.modules.inventory.domain import rules
from src.modules.inventory.infrastructure.models import MovimientoInventario, Stock
from src.modules.inventory.infrastructure.repositories import (
    MovimientoRepo,
    StockRepo,
)

# Almacén es organización transversal (data-model §1); vive en
# users/infrastructure por historia. Import de modelo (no dominio)
# permitido — mismo precedente que `application/listeners.py`.
from src.modules.users.infrastructure.models import Almacen


def aplicar_a_stock(
    session: Session, almacen_id: uuid.UUID, sku_id: uuid.UUID, delta: Decimal
) -> Stock:
    """Suma `delta` (con signo) a la fila de stock; la crea si no existe.
    Rechaza dejar la cantidad en negativo."""
    repo = StockRepo(session)
    stock = repo.get(almacen_id, sku_id, for_update=True)
    if stock is None:
        stock = repo.add(Stock(almacen_id=almacen_id, sku_id=sku_id, cantidad=Decimal(0)))
    nueva = stock.cantidad + delta
    if nueva < 0:
        raise StockInsuficiente(
            f"stock insuficiente: {stock.cantidad} disponible, se requieren {-delta}"
        )
    stock.cantidad = nueva
    return stock


def registrar_movimiento(
    session: Session,
    *,
    almacen_id: uuid.UUID,
    sku_id: uuid.UUID,
    cantidad: Decimal,
    tipo: str,
    usuario_id: uuid.UUID | None = None,
    referencia: str | None = None,
    motivo_ajuste: str | None = None,
) -> tuple[MovimientoInventario, Stock]:
    """`cantidad` con signo: + ingreso, − salida."""
    if tipo not in rules.TIPOS_MOVIMIENTO:
        raise ReglaNegocio(f"tipo de movimiento inválido: {tipo}")
    if not rules.signo_movimiento_valido(tipo, cantidad):
        raise ReglaNegocio(
            f"signo de cantidad ({cantidad}) inválido para tipo '{tipo}'"
        )
    stock = aplicar_a_stock(session, almacen_id, sku_id, cantidad)
    mov = MovimientoRepo(session).add(
        MovimientoInventario(
            almacen_id=almacen_id,
            sku_id=sku_id,
            cantidad=cantidad,
            tipo=tipo,
            motivo_ajuste=motivo_ajuste,
            referencia=referencia,
            usuario_id=usuario_id,
        )
    )
    return mov, stock


def consultar_stock(
    session: Session, almacen_id: uuid.UUID | None = None
) -> list[dict]:
    filas = StockRepo(session).list(almacen_id)
    return [
        {
            "almacen_id": s.almacen_id,
            "sku_id": s.sku_id,
            "cantidad": s.cantidad,
            "stock_minimo": s.stock_minimo,
            "bajo_minimo": rules.stock_bajo(s.cantidad, s.stock_minimo),
        }
        for s in filas
    ]


def contar_bajo_minimo(session: Session, empresa_id: uuid.UUID) -> int:
    """Cantidad de filas de stock bajo su mínimo, en almacenes de la
    empresa — para el dashboard gerencial (`core.dashboard_router`)."""
    almacen_ids = list(
        session.scalars(
            select(Almacen.id).where(
                Almacen.empresa_id == empresa_id, Almacen.deleted_at.is_(None)
            )
        )
    )
    if not almacen_ids:
        return 0
    return sum(
        1
        for s in session.scalars(select(Stock).where(Stock.almacen_id.in_(almacen_ids)))
        if rules.stock_bajo(s.cantidad, s.stock_minimo)
    )
