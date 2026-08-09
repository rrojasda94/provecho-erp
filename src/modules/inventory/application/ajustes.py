"""Casos de uso de ajuste de inventario con segregación de funciones.

Solicitar y aprobar son acciones/permisos distintos y nunca del mismo
usuario. Al aprobarse se genera el movimiento y se refleja en el stock.
"""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.inventory.application import margenes
from src.modules.inventory.application import stock as stock_uc
from src.modules.inventory.application.errors import NoEncontrado, ReglaNegocio
from src.modules.inventory.domain import rules
from src.modules.inventory.infrastructure.models import Ajuste
from src.modules.inventory.infrastructure.repositories import AjusteRepo, StockRepo
from src.modules.users.infrastructure.models import Almacen
from src.shared import auditoria


def solicitar_ajuste(
    session: Session,
    *,
    almacen_id: uuid.UUID,
    sku_id: uuid.UUID,
    cantidad: Decimal,
    motivo: str,
    solicitado_por: uuid.UUID,
) -> Ajuste:
    if motivo not in rules.MOTIVOS_AJUSTE:
        raise ReglaNegocio(f"motivo de ajuste inválido: {motivo}")
    if not rules.signo_ajuste_valido(motivo, cantidad):
        raise ReglaNegocio(
            f"signo de cantidad ({cantidad}) inválido para motivo '{motivo}'"
        )
    almacen = session.get(Almacen, almacen_id)
    if almacen is None:
        raise NoEncontrado("almacén no encontrado")
    margen, piso = margenes.margen_de_empresa(session, almacen.empresa_id)
    fila = StockRepo(session).get(almacen_id, sku_id)
    costo = margenes.costos_por_sku(session, [sku_id]).get(sku_id, Decimal(0))
    dentro_margen = rules.diferencia_dentro_margen(
        fila.cantidad if fila else Decimal(0),
        cantidad,
        margen,
        valor_diferencia=cantidad * costo,
        piso=piso,
    )
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

    comun = {
        "almacen_id": ajuste.almacen_id,
        "sku_id": ajuste.sku_id,
        "tipo": "ajuste",
        "usuario_id": aprobado_por,
        "referencia": str(ajuste.id),
        "motivo_ajuste": ajuste.motivo,
    }
    if ajuste.cantidad < 0:
        # Un ajuste negativo de un artículo con lote puede repartirse entre
        # varios lotes (FEFO): `movimiento_id` guarda el primero y todos
        # comparten `referencia`, así la traza completa sigue siendo una
        # consulta por referencia.
        movs = stock_uc.registrar_salida(session, cantidad=-ajuste.cantidad, **comun)
    else:
        mov, _ = stock_uc.registrar_movimiento(
            session, cantidad=ajuste.cantidad, **comun
        )
        movs = [mov]
    ajuste.aprobado_por = aprobado_por
    ajuste.estado = "aprobado"
    ajuste.movimiento_id = movs[0].id

    almacen = session.get(Almacen, ajuste.almacen_id)
    auditoria.registrar(
        session,
        usuario_id=aprobado_por,
        entidad="ajuste",
        entidad_id=ajuste.id,
        accion="aprobar",
        datos_antes={"estado": "pendiente"},
        datos_despues={
            "estado": "aprobado",
            "cantidad": str(ajuste.cantidad),
            "sku_id": str(ajuste.sku_id),
            "motivo": ajuste.motivo,
            "dentro_margen": ajuste.dentro_margen,
        },
        empresa_id=almacen.empresa_id if almacen else None,
        sucursal_id=almacen.sucursal_id if almacen else None,
    )

    if not ajuste.dentro_margen:
        event_bus.publish(
            "inventory.ajuste_fuera_margen",
            {"ajuste_id": str(ajuste.id), "almacen_id": str(ajuste.almacen_id)},
            session=session,
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
