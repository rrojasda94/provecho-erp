"""Validación de alcance de tenant sobre recursos de delivery (ADR-004).

Todo en `delivery` cuelga de una sucursal — repartidor, ruta y entrega
traen `sucursal_id` propio (la de la entrega, denormalizada de la venta al
asignarla) — así que el alcance se valida siempre contra
`tenant.exigir_sucursal`, igual que en `sales`.
"""

import uuid

from sqlalchemy.orm import Session

from src.core.tenant import FueraDeAlcance, Tenant
from src.modules.delivery.application.errors import NoEncontrado
from src.modules.delivery.infrastructure.models import Entrega, Repartidor, RutaReparto


def exigir_repartidor(session: Session, repartidor_id: uuid.UUID, tenant: Tenant) -> Repartidor:
    repartidor = session.get(Repartidor, repartidor_id)
    if repartidor is None or repartidor.deleted_at is not None:
        raise NoEncontrado("repartidor no encontrado")
    tenant.exigir_sucursal(repartidor.sucursal_id)
    return repartidor


def exigir_ruta(session: Session, ruta_id: uuid.UUID, tenant: Tenant) -> RutaReparto:
    ruta = session.get(RutaReparto, ruta_id)
    if ruta is None:
        raise NoEncontrado("ruta no encontrada")
    tenant.exigir_sucursal(ruta.sucursal_id)
    return ruta


def exigir_entrega(session: Session, entrega_id: uuid.UUID, tenant: Tenant) -> Entrega:
    entrega = session.get(Entrega, entrega_id)
    if entrega is None:
        raise NoEncontrado("entrega no encontrada")
    tenant.exigir_sucursal(entrega.sucursal_id)
    return entrega


def exigir_ruta_propia(session: Session, ruta: RutaReparto, usuario_id: uuid.UUID) -> None:
    """La ruta es de quien la reparte — `delivery.repartir` sin
    `delivery.despachar` solo alcanza para lo suyo, nunca la salida de un
    compañero. El router decide cuándo aplica esta segunda puerta (ver
    `_autorizar_sobre_ruta` en `api/routers.py`): un despachador la salta
    porque ya pasó la primera con su propio permiso.
    """
    repartidor = session.get(Repartidor, ruta.repartidor_id)
    if repartidor is None or repartidor.usuario_id != usuario_id:
        raise FueraDeAlcance("esta ruta no es tuya")


def exigir_entrega_de_ruta_propia(
    session: Session, entrega: Entrega, usuario_id: uuid.UUID
) -> None:
    if entrega.ruta_id is None:
        raise FueraDeAlcance("esta entrega no tiene ruta asignada")
    ruta = session.get(RutaReparto, entrega.ruta_id)
    exigir_ruta_propia(session, ruta, usuario_id)
