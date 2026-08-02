"""Mesas del salón: configuración por sucursal y mapa de ocupación.

El mapa es una lectura derivada, no un estado propio: una mesa está ocupada
si tiene una venta en `orden`. No hay campo `mesa.ocupada` a propósito —
dos fuentes de verdad para el mismo hecho se desincronizan el primer día
que alguien cobre desde otra caja.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.sales.application.errors import Conflicto, NoEncontrado
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import Mesa
from src.modules.sales.infrastructure.repositories import MesaRepo, VentaRepo


@dataclass
class MesaEnMapa:
    mesa: Mesa
    venta_id: uuid.UUID | None
    numero_orden: int | None
    comensales: int | None
    total: Decimal


def crear_mesa(
    session: Session,
    *,
    sucursal_id: uuid.UUID,
    numero: int,
    zona: str | None = None,
    capacidad: int | None = None,
) -> Mesa:
    if numero <= 0:
        raise Conflicto("el número de mesa debe ser > 0")
    repo = MesaRepo(session)
    if repo.por_numero(sucursal_id, numero) is not None:
        raise Conflicto(f"la sucursal ya tiene una mesa {numero}")
    return repo.add(
        Mesa(
            sucursal_id=sucursal_id,
            numero=numero,
            zona=zona,
            capacidad=capacidad,
            activa=True,
        )
    )


def listar_mesas(session: Session, sucursal_id: uuid.UUID) -> list[Mesa]:
    return MesaRepo(session).de_sucursal(sucursal_id)


def mapa(
    session: Session, *, sucursal_id: uuid.UUID, fecha: date | None = None
) -> list[MesaEnMapa]:
    """Todas las mesas activas de la sucursal, con la orden abierta que
    tenga cada una. Las libres vienen con `venta_id=None`."""
    dia = fecha or date.today()
    mesa_repo = MesaRepo(session)
    venta_repo = VentaRepo(session)
    abiertas = {v.mesa_id: v for v in mesa_repo.ocupadas(sucursal_id, dia)}
    salida = []
    for mesa in mesa_repo.de_sucursal(sucursal_id):
        venta = abiertas.get(mesa.id)
        total = Decimal(0)
        if venta is not None:
            total = rules.total_venta(
                [
                    (f.cantidad, f.precio_unitario, f.descuento)
                    for f in venta_repo.items(venta.id)
                ]
            )
        salida.append(
            MesaEnMapa(
                mesa=mesa,
                venta_id=venta.id if venta else None,
                numero_orden=venta.numero_orden if venta else None,
                comensales=venta.comensales if venta else None,
                total=total,
            )
        )
    return salida


def desactivar_mesa(session: Session, mesa_id: uuid.UUID) -> Mesa:
    """Baja lógica. Se niega si la mesa tiene una orden abierta: retirarla
    del mapa dejaría un pedido sin dónde cobrarse."""
    mesa = MesaRepo(session).get(mesa_id)
    if mesa is None or mesa.deleted_at is not None:
        raise NoEncontrado("mesa no encontrada")
    ocupadas = MesaRepo(session).ocupadas(mesa.sucursal_id, date.today())
    if any(v.mesa_id == mesa.id for v in ocupadas):
        raise Conflicto("la mesa tiene una orden abierta; ciérrala primero")
    mesa.activa = False
    return mesa
