"""El kardex de un artículo, resumido para graficar: qué entró y qué salió
cada semana, cómo quedó el saldo, y cuándo toca volver a comprar.

El listado de `/movimientos` dice qué pasó movimiento por movimiento; esto
responde la pregunta de quien compra, que es de ritmo y no de detalle.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.inventory.domain import rules
from src.modules.inventory.infrastructure.models import MovimientoInventario, Sku, Stock
from src.modules.users.infrastructure.models import Almacen
from src.shared import fechas

CERO = Decimal(0)


def _lunes(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


def _movimientos(
    session: Session, sku_ids: list[uuid.UUID], empresa_id: uuid.UUID | None, desde: date
) -> list[tuple[date, Decimal]]:
    """(día local, cantidad con signo) de lo que no es un traslado interno."""
    consulta = (
        select(MovimientoInventario.ts, MovimientoInventario.cantidad)
        .where(
            MovimientoInventario.sku_id.in_(sku_ids),
            MovimientoInventario.ts >= fechas.inicio_dia_utc(desde),
            MovimientoInventario.tipo.not_in(rules.TIPOS_INTERNOS),
        )
        .order_by(MovimientoInventario.ts)
    )
    if empresa_id is not None:
        consulta = consulta.join(Almacen, Almacen.id == MovimientoInventario.almacen_id).where(
            Almacen.empresa_id == empresa_id
        )
    return [(fechas.a_fecha_local(ts), cantidad) for ts, cantidad in session.execute(consulta)]


def _saldo_actual(
    session: Session, sku_ids: list[uuid.UUID], empresa_id: uuid.UUID | None
) -> tuple[Decimal, Decimal | None]:
    """Stock de la empresa entera y la suma de los mínimos declarados."""
    consulta = select(func.sum(Stock.cantidad), func.sum(Stock.stock_minimo)).where(
        Stock.sku_id.in_(sku_ids)
    )
    if empresa_id is not None:
        consulta = consulta.join(Almacen, Almacen.id == Stock.almacen_id).where(
            Almacen.empresa_id == empresa_id
        )
    cantidad, minimo = session.execute(consulta).one()
    return cantidad or CERO, minimo


def resumen_kardex(
    session: Session, articulo_id: uuid.UUID, *, empresa_id: uuid.UUID | None, dias: int
) -> dict:
    hoy = fechas.hoy()
    desde = hoy - timedelta(days=dias)
    sku_ids = list(session.scalars(select(Sku.id).where(Sku.articulo_id == articulo_id)))
    movimientos = _movimientos(session, sku_ids, empresa_id, desde) if sku_ids else []
    stock, minimo = _saldo_actual(session, sku_ids, empresa_id) if sku_ids else (CERO, None)

    entradas: dict[date, Decimal] = defaultdict(lambda: CERO)
    salidas: dict[date, Decimal] = defaultdict(lambda: CERO)
    for dia, cantidad in movimientos:
        destino = entradas if cantidad > 0 else salidas
        destino[_lunes(dia)] += abs(cantidad)

    # El saldo de cada semana se reconstruye hacia atrás desde el actual: el
    # stock es un caché de los movimientos y es el único número seguro.
    semanas = []
    saldo = stock
    lunes = _lunes(hoy)
    while lunes >= _lunes(desde):
        semanas.append(
            {
                "semana": lunes,
                "entradas": entradas[lunes],
                "salidas": salidas[lunes],
                "saldo": saldo,
            }
        )
        saldo = saldo - entradas[lunes] + salidas[lunes]
        lunes -= timedelta(days=7)
    semanas.reverse()
    # Las semanas previas al primer movimiento son saldo plano y ejes vacíos:
    # un artículo nuevo se grafica desde que empezó a moverse.
    if movimientos:
        primera = _lunes(movimientos[0][0])
        semanas = [s for s in semanas if s["semana"] >= primera]

    ventana = hoy - timedelta(days=rules.DIAS_VENTANA_CONSUMO)
    salidas_ventana = sum((-c for d, c in movimientos if c < 0 and d > ventana), CERO)
    historia = (hoy - movimientos[0][0]).days + 1 if movimientos else 0
    diario = rules.consumo_diario(salidas_ventana, historia)
    return {
        "articulo_id": articulo_id,
        "stock": stock,
        "stock_minimo": minimo,
        "consumo_diario": diario,
        "proxima_compra": rules.proxima_compra(stock, minimo, diario, hoy),
        "semanas": semanas,
    }
