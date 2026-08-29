"""Borradores del PDV: guardar, listar y descartar el ticket a medio armar
(ADR-074).

Tres operaciones y ninguna regla de negocio, porque un borrador todavía no
es un hecho de negocio: no descuenta stock, no asienta y no se cobra. Lo
único que se valida es de quién es la caja — el resto lo valida `crear_venta`
cuando el pedido de verdad sale.
"""

import uuid
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.modules.sales.application.errors import NoEncontrado
from src.modules.sales.infrastructure.models import PedidoBorrador, PuntoVenta
from src.shared import fechas


def _punto_venta(session: Session, punto_venta_id: uuid.UUID) -> PuntoVenta:
    punto = session.get(PuntoVenta, punto_venta_id)
    if punto is None:
        raise NoEncontrado("punto de venta no encontrado")
    return punto


def guardar(
    session: Session,
    *,
    borrador_id: uuid.UUID,
    punto_venta_id: uuid.UUID,
    contenido: dict,
    usuario_id: uuid.UUID,
) -> PedidoBorrador:
    """Upsert por el id que trae el PDV.

    Es upsert y no "crear o actualizar" en dos endpoints porque el navegador
    guarda con cada tecla y no puede llevar la cuenta de si esta pestaña ya
    llegó al servidor: mandar siempre el mismo `PUT` deja que un reintento
    tras un corte de red termine en el mismo estado.
    """
    punto = _punto_venta(session, punto_venta_id)
    borrador = session.get(PedidoBorrador, borrador_id)
    if borrador is None:
        borrador = PedidoBorrador(
            id=borrador_id,
            sucursal_id=punto.sucursal_id,
            punto_venta_id=punto_venta_id,
        )
        session.add(borrador)
    borrador.contenido = contenido
    # Quién lo tocó al final, no quién lo abrió: el borrador es de la caja y
    # el relevo lo sigue armando (ADR-074).
    borrador.usuario_id = usuario_id
    session.flush()
    return borrador


def listar(
    session: Session, *, punto_venta_id: uuid.UUID, dia: date | None = None
) -> list[PedidoBorrador]:
    """Los borradores vivos de esa caja, en el orden en que se abrieron.

    Filtra por jornada porque lo que quedó sin enviar ayer no es un pedido
    que alguien esté esperando: es basura de un turno que ya cerró, y
    devolverla llenaría el PDV de pestañas que nadie va a cobrar.
    """
    dia = dia or fechas.hoy()
    return list(
        session.scalars(
            select(PedidoBorrador)
            .where(
                PedidoBorrador.punto_venta_id == punto_venta_id,
                PedidoBorrador.created_at >= fechas.inicio_dia_utc(dia),
            )
            .order_by(PedidoBorrador.created_at)
        )
    )


def descartar(session: Session, borrador_id: uuid.UUID) -> None:
    """Sin `SoftDeleteMixin`: borrar de verdad.

    Un borrador descartado no tiene nada que auditar —nunca salió de la
    caja— y conservarlo obligaría a filtrarlo en cada listado para siempre.
    """
    session.execute(
        delete(PedidoBorrador).where(PedidoBorrador.id == borrador_id),
        execution_options={"synchronize_session": False},
    )


def purgar(session: Session, *, dia: date | None = None) -> int:
    """Borra los borradores de jornadas anteriores. Devuelve cuántos.

    `listar` ya no los muestra; esto es lo que evita que la tabla crezca sin
    techo con el ticket a medio armar de cada turno del año.
    """
    dia = dia or fechas.hoy()
    # `synchronize_session=False`: el criterio lo evalúa la base, no el
    # ORM en Python. Sin esto, SQLAlchemy intenta comparar la fecha con los
    # objetos que ya tenga en sesión, y en SQLite —que guarda los timestamps
    # sin zona— eso revienta contra un `datetime` con zona. La base es la que
    # tiene que decidir qué borra.
    resultado = session.execute(
        delete(PedidoBorrador).where(
            PedidoBorrador.created_at < fechas.inicio_dia_utc(dia)
        ),
        execution_options={"synchronize_session": False},
    )
    return resultado.rowcount or 0
