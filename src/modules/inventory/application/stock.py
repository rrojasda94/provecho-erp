"""Casos de uso de stock: consulta y registro de movimientos.

El stock nunca se edita directo — todo cambio pasa por
`movimiento_inventario`, que aquí se inserta y refleja en la fila `stock`.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.inventory.application import lotes as lotes_uc
from src.modules.inventory.application.errors import ReglaNegocio, StockInsuficiente
from src.modules.inventory.domain import rules
from src.modules.inventory.infrastructure.models import MovimientoInventario, Stock
from src.modules.inventory.infrastructure.repositories import (
    LoteRepo,
    MovimientoRepo,
    ReservaRepo,
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
    lote_id: uuid.UUID | None = None,
    permitir_sin_lote: bool = False,
    id: uuid.UUID | None = None,
) -> tuple[MovimientoInventario, Stock]:
    """`cantidad` con signo: + ingreso, − salida.

    Si el artículo controla lote, el movimiento también mueve `stock_lote`:
    un ingreso sin `lote_id` entra al lote del día (nada queda fuera de la
    trazabilidad) y una salida sin `lote_id` se rechaza — esa debe pasar
    por `registrar_salida`, que reparte por FEFO (ADR-015).

    `id` explícito lo usa el cliente que ya generó el identificador del
    movimiento antes de que existiera la fila (ADR-009): así un movimiento
    registrado sin conexión conserva su identidad si más tarde se
    reproduce. Los movimientos que derivan de una venta NO se sincronizan
    —el listener de la nube los genera al recibirla, empujarlos además
    duplicaría el consumo—, ver `sales/application/sincronizacion.py`.
    """
    if tipo not in rules.TIPOS_MOVIMIENTO:
        raise ReglaNegocio(f"tipo de movimiento inválido: {tipo}")
    if not rules.signo_movimiento_valido(tipo, cantidad):
        raise ReglaNegocio(
            f"signo de cantidad ({cantidad}) inválido para tipo '{tipo}'"
        )
    articulo = lotes_uc.articulo_de_sku(session, sku_id)
    if lote_id is not None and articulo.id != _articulo_del_lote(session, lote_id):
        raise ReglaNegocio("el lote no pertenece al artículo del SKU")
    if articulo.controla_lote and lote_id is None:
        if cantidad > 0:
            lote_id = lotes_uc.crear_lote(
                session,
                articulo_id=articulo.id,
                origen="ajuste" if tipo == "ajuste" else "carga_inicial",
                referencia=referencia,
            ).id
        elif not permitir_sin_lote:
            raise ReglaNegocio(
                "salida de un artículo con control de lote exige lote: "
                "usar registrar_salida (FEFO)"
            )

    stock = aplicar_a_stock(session, almacen_id, sku_id, cantidad)
    if lote_id is not None:
        lotes_uc.aplicar_a_lote(session, almacen_id, sku_id, lote_id, cantidad)
    mov = MovimientoRepo(session).add(
        MovimientoInventario(
            id=id or uuid.uuid4(),
            almacen_id=almacen_id,
            sku_id=sku_id,
            cantidad=cantidad,
            tipo=tipo,
            motivo_ajuste=motivo_ajuste,
            referencia=referencia,
            usuario_id=usuario_id,
            lote_id=lote_id,
        )
    )
    return mov, stock


def _articulo_del_lote(session: Session, lote_id: uuid.UUID) -> uuid.UUID:
    lote = LoteRepo(session).get(lote_id)
    if lote is None:
        raise ReglaNegocio("lote no encontrado")
    return lote.articulo_id


def registrar_salida(
    session: Session,
    *,
    almacen_id: uuid.UUID,
    sku_id: uuid.UUID,
    cantidad: Decimal,
    tipo: str,
    usuario_id: uuid.UUID | None = None,
    referencia: str | None = None,
    motivo_ajuste: str | None = None,
    lote_id: uuid.UUID | None = None,
    hoy: date | None = None,
) -> list[MovimientoInventario]:
    """Salida con `cantidad` POSITIVA; genera un movimiento por lote tomado.

    FEFO: vence antes, sale antes. Un `lote_id` explícito es el override
    del lote sugerido. Si el artículo no controla lote, es un movimiento
    único como siempre.
    """
    if cantidad <= 0:
        raise ReglaNegocio(f"la salida exige cantidad positiva, llegó {cantidad}")
    articulo = lotes_uc.articulo_de_sku(session, sku_id)
    if lote_id is not None or not articulo.controla_lote:
        mov, _ = registrar_movimiento(
            session,
            almacen_id=almacen_id,
            sku_id=sku_id,
            cantidad=-cantidad,
            tipo=tipo,
            usuario_id=usuario_id,
            referencia=referencia,
            motivo_ajuste=motivo_ajuste,
            lote_id=lote_id,
        )
        return [mov]

    # Comprobar el total ANTES de repartir: así una salida que no alcanza
    # falla entera, en vez de dejar consumidos los primeros lotes.
    total = StockRepo(session).get(almacen_id, sku_id)
    if total is None or total.cantidad < cantidad:
        disponible = total.cantidad if total else Decimal(0)
        raise StockInsuficiente(
            f"stock insuficiente: {disponible} disponible, se requieren {cantidad}"
        )

    disponibles = lotes_uc.disponibles_fefo(session, almacen_id, sku_id, hoy)
    asignaciones, faltante = rules.repartir_fefo(
        [(f.lote_id, f.cantidad) for f in disponibles], cantidad
    )
    movs = [
        registrar_movimiento(
            session,
            almacen_id=almacen_id,
            sku_id=sku_id,
            cantidad=-monto,
            tipo=tipo,
            usuario_id=usuario_id,
            referencia=referencia,
            motivo_ajuste=motivo_ajuste,
            lote_id=lid,
        )[0]
        for lid, monto in asignaciones
    ]
    if faltante > 0:
        # El total alcanza pero ningún lote lo respalda: stock cargado
        # antes de activar el control de lote, o todo lo demás bloqueado
        # por vencimiento. Se descuenta igual —la operación ya ocurrió— y
        # queda el movimiento sin lote como rastro de la discrepancia.
        mov, _ = registrar_movimiento(
            session,
            almacen_id=almacen_id,
            sku_id=sku_id,
            cantidad=-faltante,
            tipo=tipo,
            usuario_id=usuario_id,
            referencia=referencia,
            motivo_ajuste=motivo_ajuste,
            permitir_sin_lote=True,
        )
        movs.append(mov)
    return movs


def consultar_stock(
    session: Session,
    almacen_id: uuid.UUID | None = None,
    empresa_id: uuid.UUID | None = None,
) -> list[dict]:
    """`cantidad` es el físico; `disponible` descuenta las reservas activas
    (RN-INV-009) — es el número contra el que se compromete stock nuevo."""
    filas = StockRepo(session).list(almacen_id, empresa_id)
    reservado: dict[tuple[uuid.UUID, uuid.UUID], Decimal] = {}
    for r in ReservaRepo(session).activas(almacen_id, None, empresa_id):
        clave = (r.almacen_id, r.sku_id)
        reservado[clave] = reservado.get(clave, Decimal(0)) + r.cantidad
    return [
        {
            "almacen_id": s.almacen_id,
            "sku_id": s.sku_id,
            "cantidad": s.cantidad,
            "reservado": reservado.get((s.almacen_id, s.sku_id), Decimal(0)),
            "disponible": rules.disponible(
                s.cantidad, reservado.get((s.almacen_id, s.sku_id), Decimal(0))
            ),
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
