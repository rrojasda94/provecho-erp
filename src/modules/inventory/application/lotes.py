"""Casos de uso de lote y stock por lote (FEFO).

`stock_lote` es el detalle de `stock`: el total sigue viviendo en `stock`
y aquí se reparte por lote para poder despachar primero lo que vence antes
(RN-VNC-001..003, ADR-015). Solo aplica a artículos con `controla_lote`.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.inventory.application.errors import (
    NoEncontrado,
    ReglaNegocio,
    StockInsuficiente,
)
from src.modules.inventory.domain import rules
from src.modules.inventory.infrastructure.models import Articulo, Lote, Sku, StockLote
from src.modules.inventory.infrastructure.repositories import LoteRepo, StockLoteRepo

ORIGENES = {"compra", "produccion", "carga_inicial", "ajuste"}
CONDICIONES = {"refrigerado", "congelado", "ambiente"}


def articulo_de_sku(session: Session, sku_id: uuid.UUID) -> Articulo:
    sku = session.get(Sku, sku_id)
    if sku is None:
        raise NoEncontrado("SKU no encontrado")
    articulo = session.get(Articulo, sku.articulo_id)
    if articulo is None:
        raise NoEncontrado("artículo del SKU no encontrado")
    return articulo


def crear_lote(
    session: Session,
    *,
    articulo_id: uuid.UUID,
    codigo: str | None = None,
    fecha_vencimiento: date | None = None,
    fecha_elaboracion: date | None = None,
    origen: str = "carga_inicial",
    referencia: str | None = None,
    condicion_almacenamiento: str | None = None,
    hoy: date | None = None,
) -> Lote:
    """Devuelve el lote existente con ese código o lo crea (RN-LOT-001).

    Sin código explícito lo deriva del vencimiento: dos recepciones del
    mismo artículo que vencen el mismo día son el mismo lote.
    """
    if origen not in ORIGENES:
        raise ReglaNegocio(f"origen de lote inválido: {origen}")
    if condicion_almacenamiento is not None and condicion_almacenamiento not in CONDICIONES:
        raise ReglaNegocio(
            f"condición de almacenamiento inválida: {condicion_almacenamiento}"
        )
    codigo = codigo or rules.codigo_lote_auto(fecha_vencimiento or (hoy or date.today()))
    repo = LoteRepo(session)
    existente = repo.get_by_codigo(articulo_id, codigo)
    if existente is not None:
        return existente
    return repo.add(
        Lote(
            articulo_id=articulo_id,
            codigo=codigo,
            fecha_vencimiento=fecha_vencimiento,
            fecha_elaboracion=fecha_elaboracion,
            origen=origen,
            referencia=referencia,
            condicion_almacenamiento=condicion_almacenamiento,
        )
    )


def aplicar_a_lote(
    session: Session,
    almacen_id: uuid.UUID,
    sku_id: uuid.UUID,
    lote_id: uuid.UUID,
    delta: Decimal,
) -> StockLote:
    """Suma `delta` (con signo) al saldo de ese lote en ese almacén."""
    repo = StockLoteRepo(session)
    fila = repo.get(almacen_id, sku_id, lote_id, for_update=True)
    if fila is None:
        fila = repo.add(
            StockLote(
                almacen_id=almacen_id,
                sku_id=sku_id,
                lote_id=lote_id,
                cantidad=Decimal(0),
                estado="disponible",
            )
        )
    nueva = fila.cantidad + delta
    if nueva < 0:
        raise StockInsuficiente(
            f"lote {lote_id}: {fila.cantidad} disponible, se requieren {-delta}"
        )
    fila.cantidad = nueva
    if fila.estado != "bloqueado":
        fila.estado = "agotado" if nueva == 0 else "disponible"
    return fila


def _bloquear(session: Session, fila: StockLote, lote: Lote) -> None:
    fila.estado = "bloqueado"
    event_bus.publish(
        "inventory.lote_vencido_detectado",
        {
            "lote_id": str(lote.id),
            "almacen_id": str(fila.almacen_id),
            "sku_id": str(fila.sku_id),
            "fecha_vencimiento": lote.fecha_vencimiento.isoformat(),
            "cantidad": str(fila.cantidad),
        },
        session=session,
    )


def disponibles_fefo(
    session: Session,
    almacen_id: uuid.UUID,
    sku_id: uuid.UUID,
    hoy: date | None = None,
) -> list[StockLote]:
    """Lotes que el picking puede tomar, en orden FEFO.

    De paso bloquea el lote vencido que seguía disponible y publica
    `inventory.lote_vencido_detectado`: el momento de tocarlo es el momento
    en que se descubre, sin depender de que alguien corra el barrido.
    """
    hoy = hoy or date.today()
    resultado: list[StockLote] = []
    for fila in StockLoteRepo(session).fefo(almacen_id, sku_id):
        lote = session.get(Lote, fila.lote_id)
        if rules.lote_vencido(lote.fecha_vencimiento, hoy):
            if fila.estado != "bloqueado":
                _bloquear(session, fila, lote)
            continue
        if fila.estado == "bloqueado":
            continue
        resultado.append(fila)
    return resultado


def bloquear_vencidos(
    session: Session,
    almacen_id: uuid.UUID | None = None,
    empresa_id: uuid.UUID | None = None,
    hoy: date | None = None,
) -> list[StockLote]:
    """Barrido explícito: bloquea todo lote vencido que aún tenga saldo
    disponible. Lo mismo que hace el picking, pero sin esperar a la salida."""
    hoy = hoy or date.today()
    bloqueados = []
    for fila, lote in StockLoteRepo(session).list(almacen_id, None, empresa_id):
        if (
            fila.estado == "disponible"
            and fila.cantidad > 0
            and rules.lote_vencido(lote.fecha_vencimiento, hoy)
        ):
            _bloquear(session, fila, lote)
            bloqueados.append(fila)
    return bloqueados


def listar(
    session: Session,
    *,
    almacen_id: uuid.UUID | None = None,
    sku_id: uuid.UUID | None = None,
    empresa_id: uuid.UUID | None = None,
    por_vencer_dias: int | None = None,
    hoy: date | None = None,
) -> list[dict]:
    hoy = hoy or date.today()
    filas = StockLoteRepo(session).list(almacen_id, sku_id, empresa_id)
    if por_vencer_dias is not None:
        filas = [
            (sl, lote)
            for sl, lote in filas
            if rules.por_vencer(lote.fecha_vencimiento, hoy, por_vencer_dias)
        ]
    return [
        {
            "lote_id": lote.id,
            "codigo": lote.codigo,
            "articulo_id": lote.articulo_id,
            "almacen_id": sl.almacen_id,
            "sku_id": sl.sku_id,
            "cantidad": sl.cantidad,
            "estado": sl.estado,
            "fecha_vencimiento": lote.fecha_vencimiento,
            "vencido": rules.lote_vencido(lote.fecha_vencimiento, hoy),
        }
        for sl, lote in filas
    ]


def lotes_del_articulo(session: Session, articulo_id: uuid.UUID) -> list[Lote]:
    return list(
        session.scalars(
            select(Lote)
            .where(Lote.articulo_id == articulo_id)
            .order_by(Lote.fecha_vencimiento.is_(None), Lote.fecha_vencimiento)
        )
    )
