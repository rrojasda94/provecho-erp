"""Mesas del salón: configuración por sucursal y mapa de ocupación.

El mapa es una lectura derivada, no un estado propio: una mesa está ocupada
si tiene una venta en `orden`. No hay campo `mesa.ocupada` a propósito —
dos fuentes de verdad para el mismo hecho se desincronizan el primer día
que alguien cobre desde otra caja.

El salón se numera 1..n sin huecos (RN-MDC-004): el número lo asigna el
sistema al crear (siguiente disponible) y solo se libera al retirar la
mesa de número más alto (RN-MDC-006). Ni crear ni retirar aceptan un
número a mano — la única forma de tener "la mesa 5" es que sea la quinta
que exista.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.sales.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import Mesa
from src.modules.sales.infrastructure.repositories import MesaRepo, VentaRepo
from src.shared import auditoria, fechas


@dataclass
class MesaEnMapa:
    mesa: Mesa
    venta_id: uuid.UUID | None
    numero_orden: int | None
    comensales: int | None
    total: Decimal


def _primera_celda_libre(session: Session, sucursal_id: uuid.UUID) -> tuple[int, int]:
    ocupadas = MesaRepo(session).posiciones_ocupadas(sucursal_id)
    indice = 0
    while rules.posicion_por_defecto(indice) in ocupadas:
        indice += 1
    return rules.posicion_por_defecto(indice)


def _validar_celda(pos_x: int, pos_y: int) -> None:
    if pos_x < 0 or pos_y < 0:
        raise ReglaNegocio("la celda del plano no puede ser negativa")
    if pos_x >= rules.MESA_COLUMNAS:
        raise ReglaNegocio(
            f"el plano tiene {rules.MESA_COLUMNAS} columnas; la celda pedida se sale"
        )


def crear_mesa(
    session: Session,
    *,
    sucursal_id: uuid.UUID,
    zona: str | None = None,
    capacidad: int | None = None,
    pos_x: int | None = None,
    pos_y: int | None = None,
    actor_id: uuid.UUID | None = None,
) -> Mesa:
    """Numera automático: siguiente número sobre las mesas activas, o el
    de una mesa retirada con ventas si quedó libre (reactivarla evita
    insertar una fila y chocar contra el único de `numero`)."""
    repo = MesaRepo(session)
    activas = repo.de_sucursal(sucursal_id, solo_activas=True)
    numero = (max((m.numero for m in activas), default=0)) + 1

    if pos_x is not None or pos_y is not None:
        if pos_x is None or pos_y is None:
            raise ReglaNegocio("pos_x y pos_y se indican juntas")
        _validar_celda(pos_x, pos_y)
        if repo.en_posicion(sucursal_id, pos_x, pos_y) is not None:
            raise Conflicto(f"ya hay una mesa en la celda ({pos_x}, {pos_y})")
    else:
        pos_x, pos_y = _primera_celda_libre(session, sucursal_id)

    inactiva = repo.por_numero(sucursal_id, numero)
    if inactiva is not None:
        inactiva.zona = zona
        inactiva.capacidad = capacidad
        inactiva.pos_x = pos_x
        inactiva.pos_y = pos_y
        inactiva.activa = True
        mesa = inactiva
    else:
        mesa = repo.add(
            Mesa(
                sucursal_id=sucursal_id,
                numero=numero,
                zona=zona,
                capacidad=capacidad,
                pos_x=pos_x,
                pos_y=pos_y,
                activa=True,
            )
        )
    auditoria.registrar(
        session,
        usuario_id=actor_id,
        entidad="mesa",
        entidad_id=mesa.id,
        accion="crear",
        sucursal_id=sucursal_id,
        datos_despues={"numero": str(mesa.numero)},
    )
    return mesa


def listar_mesas(session: Session, sucursal_id: uuid.UUID) -> list[Mesa]:
    return MesaRepo(session).de_sucursal(sucursal_id)


def editar_mesa(
    session: Session,
    mesa_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
    **campos,
) -> Mesa:
    """El número no se edita (RN-MDC-004): solo `zona`, `capacidad`, `pos_x`
    y `pos_y` en `campos` (los que vinieron seteados en el PATCH). Una
    orden abierta bloquea el cambio — mover o renombrar una mesa que el
    mozo está sirviendo confunde más de lo que ordena (RN-MDC-005)."""
    repo = MesaRepo(session)
    mesa = repo.get(mesa_id)
    if mesa is None:
        raise NoEncontrado("mesa no encontrada")
    if repo.orden_abierta(mesa.id) is not None:
        raise Conflicto("la mesa tiene una orden abierta; ciérrala primero")

    antes = {"zona": mesa.zona, "capacidad": mesa.capacidad}
    if "zona" in campos:
        mesa.zona = campos["zona"]
    if "capacidad" in campos:
        mesa.capacidad = campos["capacidad"]

    nuevo_x = campos.get("pos_x", mesa.pos_x)
    nuevo_y = campos.get("pos_y", mesa.pos_y)
    if (nuevo_x, nuevo_y) != (mesa.pos_x, mesa.pos_y):
        _validar_celda(nuevo_x, nuevo_y)
        choque = repo.en_posicion(mesa.sucursal_id, nuevo_x, nuevo_y)
        if choque is not None and choque.id != mesa.id:
            raise Conflicto(f"ya hay una mesa en la celda ({nuevo_x}, {nuevo_y})")
        mesa.pos_x = nuevo_x
        mesa.pos_y = nuevo_y

    auditoria.registrar(
        session,
        usuario_id=actor_id,
        entidad="mesa",
        entidad_id=mesa.id,
        accion="editar",
        sucursal_id=mesa.sucursal_id,
        datos_antes={k: str(v) for k, v in antes.items()},
        datos_despues={"zona": str(mesa.zona), "capacidad": str(mesa.capacidad)},
    )
    return mesa


def mapa(
    session: Session, *, sucursal_id: uuid.UUID, fecha: date | None = None
) -> list[MesaEnMapa]:
    """Todas las mesas activas de la sucursal, con la orden abierta que
    tenga cada una. Las libres vienen con `venta_id=None`."""
    dia = fecha or fechas.hoy()
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


def eliminar_mesa(
    session: Session, mesa_id: uuid.UUID, actor_id: uuid.UUID | None = None
) -> None:
    """Retira la mesa de número más alto (RN-MDC-006): es la única que se
    puede quitar sin dejar un hueco en el 1..n ni renumerar el resto —
    renumerar reescribiría a qué mesa apuntó una venta ya cerrada.

    Se borra la fila si la mesa nunca tuvo ventas; si tuvo, queda
    `activa=False` conservando número y celda para que el historial
    resuelva."""
    repo = MesaRepo(session)
    mesa = repo.get(mesa_id)
    if mesa is None:
        raise NoEncontrado("mesa no encontrada")
    if repo.orden_abierta(mesa.id) is not None:
        raise Conflicto("la mesa tiene una orden abierta; ciérrala primero")
    mayor = repo.mesa_mayor(mesa.sucursal_id)
    if mayor is not None and mayor.id != mesa.id:
        raise Conflicto(
            f"el salón se numera 1..n; retira primero la mesa {mayor.numero}"
        )

    auditoria.registrar(
        session,
        usuario_id=actor_id,
        entidad="mesa",
        entidad_id=mesa.id,
        accion="eliminar",
        sucursal_id=mesa.sucursal_id,
        datos_antes={"numero": str(mesa.numero)},
    )
    if repo.tuvo_ventas(mesa.id):
        mesa.activa = False
    else:
        repo.eliminar(mesa)
