"""Casos de uso de reserva de stock (RN-INV-009..012).

Una reserva es una promesa sobre stock que sigue físicamente en el
almacén: no genera `movimiento_inventario` ni toca `stock`. Existe para
que dos solicitudes no se prometan el mismo saco de harina.

**Reservar bloquea, consumir no.** Comprometer stock nuevo (aprobar una
solicitud) exige disponible suficiente; en cambio una venta o un consumo
de producción NUNCA se frenan por una reserva — esa operación ya ocurrió
en el mundo real y negarla en el ERP solo desincroniza los libros. Si eso
deja el disponible en negativo, es información: hay una promesa sin
respaldo y alguien tiene que liberarla o reponer.
"""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.inventory.application.errors import (
    NoEncontrado,
    ReglaNegocio,
    StockInsuficiente,
)
from src.modules.inventory.domain import rules
from src.modules.inventory.infrastructure.models import ReservaStock
from src.modules.inventory.infrastructure.repositories import ReservaRepo, StockRepo


def reservado(
    session: Session, almacen_id: uuid.UUID, sku_id: uuid.UUID
) -> Decimal:
    return sum(
        (r.cantidad for r in ReservaRepo(session).activas(almacen_id, sku_id)),
        Decimal(0),
    )


def disponible(
    session: Session, almacen_id: uuid.UUID, sku_id: uuid.UUID
) -> Decimal:
    fila = StockRepo(session).get(almacen_id, sku_id)
    fisico = fila.cantidad if fila else Decimal(0)
    return rules.disponible(fisico, reservado(session, almacen_id, sku_id))


def reservar(
    session: Session,
    *,
    almacen_id: uuid.UUID,
    sku_id: uuid.UUID,
    cantidad: Decimal,
    tipo: str,
    creado_por: uuid.UUID,
    referencia_id: uuid.UUID | None = None,
    motivo: str | None = None,
) -> ReservaStock:
    if tipo not in rules.TIPOS_RESERVA:
        raise ReglaNegocio(f"tipo de reserva inválido: {tipo}")
    if tipo == "merma":
        if motivo not in rules.MOTIVOS_RESERVA_MERMA:
            raise ReglaNegocio(f"motivo de reserva de merma inválido: {motivo}")
    elif motivo is not None:
        raise ReglaNegocio("`motivo` solo aplica a reservas de tipo merma")
    if cantidad <= 0:
        raise ReglaNegocio(f"la reserva exige cantidad positiva, llegó {cantidad}")

    libre = disponible(session, almacen_id, sku_id)
    if cantidad > libre:
        raise StockInsuficiente(
            f"stock disponible insuficiente: {libre} libre (físico menos "
            f"reservas activas), se requieren {cantidad}"
        )
    return ReservaRepo(session).add(
        ReservaStock(
            almacen_id=almacen_id,
            sku_id=sku_id,
            cantidad=cantidad,
            tipo=tipo,
            referencia_id=referencia_id,
            motivo=motivo,
            estado="activa",
            creado_por=creado_por,
        )
    )


def liberar(
    session: Session, reserva_id: uuid.UUID, liberado_por: uuid.UUID
) -> ReservaStock:
    """Suelta una reserva a mano: el central redistribuye ante
    desabastecimiento o sobredemanda (RN-INV-011)."""
    reserva = ReservaRepo(session).get(reserva_id)
    if reserva is None:
        raise NoEncontrado("reserva no encontrada")
    return _liberar(reserva, liberado_por)


def _liberar(reserva: ReservaStock, liberado_por: uuid.UUID | None) -> ReservaStock:
    if reserva.estado != "activa":
        raise ReglaNegocio(f"la reserva ya está {reserva.estado}")
    reserva.estado = "liberada"
    reserva.liberado_por = liberado_por
    return reserva


def liberar_por_referencia(
    session: Session, referencia_id: uuid.UUID, liberado_por: uuid.UUID | None = None
) -> list[ReservaStock]:
    """Al cancelarse el documento que originó las reservas, vuelven a
    disponible solas (RN-INV-010)."""
    reservas = ReservaRepo(session).por_referencia(referencia_id)
    for reserva in reservas:
        _liberar(reserva, liberado_por)
    return reservas


def consumir_por_referencia(
    session: Session, referencia_id: uuid.UUID, sku_id: uuid.UUID
) -> None:
    """La promesa se cumplió: el stock salió de verdad. Cerrar la reserva
    es obligatorio o el disponible quedaría descontado dos veces —una por
    la reserva viva y otra por el movimiento que ya bajó el físico."""
    for reserva in ReservaRepo(session).por_referencia(referencia_id):
        if reserva.sku_id == sku_id:
            reserva.estado = "consumida"


def listar(
    session: Session,
    *,
    almacen_id: uuid.UUID | None = None,
    sku_id: uuid.UUID | None = None,
    empresa_id: uuid.UUID | None = None,
) -> list[ReservaStock]:
    return ReservaRepo(session).activas(almacen_id, sku_id, empresa_id)
