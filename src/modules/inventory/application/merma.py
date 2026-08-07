"""Merma: stock que sigue en el almacén pero ya no sirve (RN-INV-012/017).

**No hay tabla `stock_merma`.** El modelo de datos la anticipaba como
"subtipo de stock reservado", y eso es exactamente lo que `reserva_stock`
ya hace: la merma es una reserva de tipo `merma` con su motivo
(`devolucion` | `rechazo_sucursal` | `auditoria`). Una tabla aparte
duplicaría almacén, SKU, cantidad y estado para expresar la misma idea —lo
que está físicamente ahí y no se puede vender— y obligaría a restar dos
cosas distintas al calcular el disponible. Ver ADR-028.

El ciclo tiene dos pasos y **eso es la regla**, no una comodidad:

1. **Registrar** aparta el stock. No sale del almacén ni se pierde todavía:
   queda pendiente de auditoría, que es el estado que RN-INV-012 describe.
   Quien lo detecta lo registra.
2. **Resolver** decide su destino (RN-INV-019). `reintegro` lo devuelve a
   disponible —la auditoría dijo que servía— y `desecho` recién ahí saca el
   stock y publica `inventory.merma_registrada`, que es lo que `accounting`
   asienta como pérdida. Lo resuelve otro usuario, igual que un ajuste: el
   que declara la merma no firma su baja.

Por eso el asiento va al desechar y no al registrar: mientras la auditoría
no decida, no hay pérdida que asentar — sería asentarla y reversarla en la
mitad de los casos.
"""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.inventory.application import lotes as lotes_uc
from src.modules.inventory.application import margenes
from src.modules.inventory.application import reservas as reservas_uc
from src.modules.inventory.application import stock as stock_uc
from src.modules.inventory.application.errors import NoEncontrado, ReglaNegocio
from src.modules.inventory.domain import rules
from src.modules.inventory.infrastructure.models import ReservaStock
from src.modules.inventory.infrastructure.repositories import LoteRepo, ReservaRepo

DESTINOS = ("desecho", "reintegro")


def registrar_merma(
    session: Session,
    *,
    almacen_id: uuid.UUID,
    sku_id: uuid.UUID,
    cantidad: Decimal,
    motivo: str,
    creado_por: uuid.UUID,
    lote_id: uuid.UUID | None = None,
    referencia_id: uuid.UUID | None = None,
) -> ReservaStock:
    """Aparta stock inservible. No lo saca del almacén: lo saca de la venta.

    Reserva y no movimiento porque el producto **sigue estando ahí** —hasta
    que alguien lo tire, sigue ocupando el estante y contando en el conteo
    físico—. Descontarlo acá haría que el conteo cíclico lo declarara
    sobrante al día siguiente.
    """
    if motivo not in rules.MOTIVOS_RESERVA_MERMA:
        raise ReglaNegocio(f"motivo de merma inválido: {motivo}")
    if lote_id is not None:
        articulo = lotes_uc.articulo_de_sku(session, sku_id)
        lote = LoteRepo(session).get(lote_id)
        if lote is None:
            raise NoEncontrado("lote no encontrado")
        if lote.articulo_id != articulo.id:
            raise ReglaNegocio("el lote no pertenece al artículo del SKU")

    reserva = reservas_uc.reservar(
        session,
        almacen_id=almacen_id,
        sku_id=sku_id,
        cantidad=cantidad,
        tipo="merma",
        motivo=motivo,
        creado_por=creado_por,
        referencia_id=referencia_id,
    )
    reserva.lote_id = lote_id
    return reserva


def resolver_merma(
    session: Session,
    reserva_id: uuid.UUID,
    *,
    destino: str,
    resuelto_por: uuid.UUID,
) -> ReservaStock:
    """Cierra el ciclo: `desecho` saca el stock, `reintegro` lo devuelve."""
    if destino not in DESTINOS:
        raise ReglaNegocio(f"destino de merma inválido: {destino}")
    reserva = ReservaRepo(session).get(reserva_id)
    if reserva is None:
        raise NoEncontrado("merma no encontrada")
    if reserva.tipo != "merma":
        raise ReglaNegocio("esa reserva no es una merma")
    if reserva.estado != "activa":
        raise ReglaNegocio(f"la merma ya está {reserva.estado}")
    if not rules.puede_aprobar(reserva.creado_por, resuelto_por):
        raise ReglaNegocio("quien registró la merma no resuelve su destino")

    if destino == "reintegro":
        reserva.estado = "liberada"
        reserva.liberado_por = resuelto_por
        return reserva

    # Desecho: el lote apartado sale, y sale **ese** — no el que FEFO
    # elegiría. El motivo va escrito porque saltearse FEFO siempre lo exige
    # (RN-LOT-004) y acá la razón es justamente que este lote no sirve.
    stock_uc.registrar_salida(
        session,
        almacen_id=reserva.almacen_id,
        sku_id=reserva.sku_id,
        cantidad=reserva.cantidad,
        tipo="ajuste",
        motivo_ajuste="merma",
        usuario_id=resuelto_por,
        referencia=str(reserva.id),
        lote_id=reserva.lote_id,
        motivo_lote=f"desecho de merma por {reserva.motivo}",
    )
    reserva.estado = "consumida"
    reserva.liberado_por = resuelto_por

    costo = margenes.costos_por_sku(session, [reserva.sku_id]).get(
        reserva.sku_id, Decimal(0)
    )
    event_bus.publish(
        "inventory.merma_registrada",
        {
            "almacen_id": str(reserva.almacen_id),
            "sku_id": str(reserva.sku_id),
            "lote_id": str(reserva.lote_id) if reserva.lote_id else None,
            "cantidad": str(reserva.cantidad),
            "motivo": reserva.motivo,
            # Valorizada por el emisor, como el faltante de un traslado: el
            # costo es dato de `inventory`.
            "monto": str(reserva.cantidad * costo),
        },
        session=session,
    )
    return reserva


def listar_mermas(
    session: Session,
    *,
    almacen_id: uuid.UUID | None = None,
    empresa_id: uuid.UUID | None = None,
) -> list[ReservaStock]:
    """Las mermas **pendientes de resolver**: es la bandeja de la auditoría."""
    return [
        r
        for r in ReservaRepo(session).activas(almacen_id, None, empresa_id)
        if r.tipo == "merma"
    ]
