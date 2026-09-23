"""El kardex de un artículo, resumido para graficar: qué entró y qué salió
cada semana, cómo quedó el saldo, y cuándo toca volver a comprar.

El listado de `/movimientos` dice qué pasó movimiento por movimiento; esto
responde la pregunta de quien compra, que es de ritmo y no de detalle.

Se mira en tres ámbitos (ADR-108, enmienda 2026-09-23): la empresa entera,
una sede (sus almacenes sumados) o un almacén. En la empresa los traslados
internos se anulan y no cuentan; en una sede o un almacén son justamente su
reposición —lo que llega del central— y sus envíos, así que cuentan.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.inventory.domain import rules
from src.modules.inventory.infrastructure.models import MovimientoInventario, Sku, Stock
from src.modules.users.infrastructure.models import Almacen, Sucursal
from src.shared import fechas

CERO = Decimal(0)


@dataclass(frozen=True)
class Ambito:
    """Dónde se mira el artículo. Sin almacén ni sucursal, la empresa."""

    empresa_id: uuid.UUID | None
    almacen_id: uuid.UUID | None = None
    sucursal_id: uuid.UUID | None = None

    @property
    def acotado(self) -> bool:
        return self.almacen_id is not None or self.sucursal_id is not None


def _lunes(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


def _acotar(consulta, columna_almacen, ambito: Ambito):
    """Filtra por el almacén del movimiento o del stock según el ámbito."""
    if ambito.almacen_id is not None:
        return consulta.where(columna_almacen == ambito.almacen_id)
    consulta = consulta.join(Almacen, Almacen.id == columna_almacen)
    if ambito.sucursal_id is not None:
        consulta = consulta.where(Almacen.sucursal_id == ambito.sucursal_id)
    if ambito.empresa_id is not None:
        consulta = consulta.where(Almacen.empresa_id == ambito.empresa_id)
    return consulta


def _movimientos(
    session: Session, sku_ids: list[uuid.UUID], ambito: Ambito, desde: date
) -> list[tuple[date, Decimal]]:
    """(día local, cantidad con signo) de lo que cuenta en el ámbito."""
    consulta = (
        select(MovimientoInventario.ts, MovimientoInventario.cantidad)
        .where(
            MovimientoInventario.sku_id.in_(sku_ids),
            MovimientoInventario.ts >= fechas.inicio_dia_utc(desde),
        )
        .order_by(MovimientoInventario.ts)
    )
    if not ambito.acotado:
        consulta = consulta.where(MovimientoInventario.tipo.not_in(rules.TIPOS_INTERNOS))
    consulta = _acotar(consulta, MovimientoInventario.almacen_id, ambito)
    return [(fechas.a_fecha_local(ts), cantidad) for ts, cantidad in session.execute(consulta)]


def _saldo_actual(
    session: Session, sku_ids: list[uuid.UUID], ambito: Ambito
) -> tuple[Decimal, Decimal | None]:
    """Stock del ámbito y la suma de los mínimos declarados en él."""
    consulta = select(func.sum(Stock.cantidad), func.sum(Stock.stock_minimo)).where(
        Stock.sku_id.in_(sku_ids)
    )
    cantidad, minimo = session.execute(_acotar(consulta, Stock.almacen_id, ambito)).one()
    return cantidad or CERO, minimo


def _semanas(movimientos, stock: Decimal, desde: date, hoy: date) -> list[dict]:
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
    return semanas


def _ritmo(movimientos, stock: Decimal, minimo: Decimal | None, hoy: date) -> dict:
    ventana = hoy - timedelta(days=rules.DIAS_VENTANA_CONSUMO)
    recientes = [(d, c) for d, c in movimientos if d > ventana]
    salidas = sum((-c for _, c in recientes if c < 0), CERO)
    historia = (hoy - movimientos[0][0]).days + 1 if movimientos else 0
    diario = rules.consumo_diario(salidas, historia)
    return {
        "stock": stock,
        "stock_minimo": minimo,
        "consumo_diario": diario,
        "proxima_compra": rules.proxima_compra(stock, minimo, diario, hoy),
        # Días distintos con alguna entrada: cuántas veces se repuso.
        "reposiciones_90_dias": len({d for d, c in recientes if c > 0}),
    }


def _skus(session: Session, articulo_id: uuid.UUID) -> list[uuid.UUID]:
    return list(session.scalars(select(Sku.id).where(Sku.articulo_id == articulo_id)))


def resumen_kardex(
    session: Session, articulo_id: uuid.UUID, *, ambito: Ambito, dias: int
) -> dict:
    hoy = fechas.hoy()
    desde = hoy - timedelta(days=dias)
    sku_ids = _skus(session, articulo_id)
    movimientos = _movimientos(session, sku_ids, ambito, desde) if sku_ids else []
    stock, minimo = _saldo_actual(session, sku_ids, ambito) if sku_ids else (CERO, None)
    return {
        "articulo_id": articulo_id,
        **_ritmo(movimientos, stock, minimo, hoy),
        "semanas": _semanas(movimientos, stock, desde, hoy),
    }


def kardex_por_almacen(
    session: Session, articulo_id: uuid.UUID, *, empresa_id: uuid.UUID | None
) -> list[dict]:
    """Cómo está cada almacén que maneja el artículo: la realidad de cada sede
    lado a lado, ordenada por lo que se agota primero.

    ponytail: una consulta de movimientos por almacén. Un artículo vive en
    decenas de almacenes, no en miles; si eso cambia, agrupar en una sola.
    """
    hoy = fechas.hoy()
    sku_ids = _skus(session, articulo_id)
    if not sku_ids:
        return []
    consulta = (
        select(Almacen.id, Almacen.nombre, Sucursal.id, Sucursal.nombre)
        .join(Stock, Stock.almacen_id == Almacen.id)
        .outerjoin(Sucursal, Sucursal.id == Almacen.sucursal_id)
        .where(Stock.sku_id.in_(sku_ids), Almacen.deleted_at.is_(None))
        .distinct()
    )
    if empresa_id is not None:
        consulta = consulta.where(Almacen.empresa_id == empresa_id)
    filas = []
    desde = hoy - timedelta(days=rules.DIAS_VENTANA_CONSUMO)
    for almacen_id, almacen, sucursal_id, sucursal in session.execute(consulta).all():
        ambito = Ambito(empresa_id=empresa_id, almacen_id=almacen_id)
        movimientos = _movimientos(session, sku_ids, ambito, desde)
        stock, minimo = _saldo_actual(session, sku_ids, ambito)
        filas.append(
            {
                "almacen_id": almacen_id,
                "almacen": almacen,
                "sucursal_id": sucursal_id,
                "sucursal": sucursal,
                **_ritmo(movimientos, stock, minimo, hoy),
            }
        )
    # Lo que se agota primero arriba; lo que no se consume, al final.
    return sorted(filas, key=lambda f: (f["proxima_compra"] is None, f["proxima_compra"] or hoy))
