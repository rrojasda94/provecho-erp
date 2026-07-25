"""Casos de uso de ajuste de inventario con segregación de funciones.

Solicitar y aprobar son acciones/permisos distintos y nunca del mismo
usuario. Al aprobarse se genera el movimiento y se refleja en el stock.
"""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.inventory.application import stock as stock_uc
from src.modules.inventory.application.errors import NoEncontrado, ReglaNegocio
from src.modules.inventory.domain import rules
from src.modules.inventory.infrastructure.models import Ajuste
from src.modules.inventory.infrastructure.repositories import AjusteRepo


def solicitar_ajuste(
    session: Session,
    *,
    almacen_id: uuid.UUID,
    sku_id: uuid.UUID,
    cantidad: Decimal,
    motivo: str,
    solicitado_por: uuid.UUID,
    dentro_margen: bool = True,
) -> Ajuste:
    if motivo not in rules.MOTIVOS_AJUSTE:
        raise ReglaNegocio(f"motivo de ajuste inválido: {motivo}")
    return AjusteRepo(session).add(
        Ajuste(
            almacen_id=almacen_id,
            sku_id=sku_id,
            cantidad=cantidad,
            motivo=motivo,
            solicitado_por=solicitado_por,
            dentro_margen=dentro_margen,
            estado="pendiente",
        )
    )


def aprobar_ajuste(
    session: Session, ajuste_id: uuid.UUID, aprobado_por: uuid.UUID
) -> Ajuste:
    ajuste = AjusteRepo(session).get(ajuste_id)
    if ajuste is None:
        raise NoEncontrado("ajuste no encontrado")
    if ajuste.estado != "pendiente":
        raise ReglaNegocio(f"el ajuste ya está {ajuste.estado}")
    if not rules.puede_aprobar(ajuste.solicitado_por, aprobado_por):
        raise ReglaNegocio("el aprobador no puede ser el solicitante del ajuste")

    mov, _ = stock_uc.registrar_movimiento(
        session,
        almacen_id=ajuste.almacen_id,
        sku_id=ajuste.sku_id,
        cantidad=ajuste.cantidad,
        tipo="ajuste",
        usuario_id=aprobado_por,
        referencia=str(ajuste.id),
        motivo_ajuste=ajuste.motivo,
    )
    ajuste.aprobado_por = aprobado_por
    ajuste.estado = "aprobado"
    ajuste.movimiento_id = mov.id

    if not ajuste.dentro_margen:
        event_bus.publish(
            "inventory.ajuste_fuera_margen",
            {"ajuste_id": str(ajuste.id), "almacen_id": str(ajuste.almacen_id)},
        )
    return ajuste


def rechazar_ajuste(
    session: Session, ajuste_id: uuid.UUID, aprobado_por: uuid.UUID
) -> Ajuste:
    ajuste = AjusteRepo(session).get(ajuste_id)
    if ajuste is None:
        raise NoEncontrado("ajuste no encontrado")
    if ajuste.estado != "pendiente":
        raise ReglaNegocio(f"el ajuste ya está {ajuste.estado}")
    ajuste.aprobado_por = aprobado_por
    ajuste.estado = "rechazado"
    return ajuste
