"""Inventario de POS de pago con tarjeta (RN-POS-009/010).

Contabilidad da de alta cada terminal con su serie y código de comercio, y
mantiene al menos uno de emergencia (`sucursal_id` en NULL) para cubrir una
falla sin que la sucursal deje de cobrar con tarjeta.
"""

import uuid

from sqlalchemy.orm import Session

from src.modules.accounting.application.errors import Conflicto, NoEncontrado
from src.modules.accounting.infrastructure.models import PosTarjeta
from src.modules.accounting.infrastructure.repositories import PosTarjetaRepo

ESTADOS = ("operativo", "averiado", "baja")


def registrar_pos(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    serie: str,
    codigo_comercio: str,
    sucursal_id: uuid.UUID | None = None,
    operador: str | None = None,
    es_emergencia: bool = False,
) -> PosTarjeta:
    repo = PosTarjetaRepo(session)
    if repo.get_by_serie(serie) is not None:
        raise Conflicto(f"ya existe un POS con la serie {serie}")
    return repo.add(
        PosTarjeta(
            empresa_id=empresa_id,
            sucursal_id=sucursal_id,
            serie=serie.strip(),
            codigo_comercio=codigo_comercio.strip(),
            operador=operador,
            es_emergencia=es_emergencia,
        )
    )


def actualizar_pos(
    session: Session,
    pos_id: uuid.UUID,
    *,
    estado: str | None = None,
    sucursal_id: uuid.UUID | None = None,
    es_emergencia: bool | None = None,
) -> PosTarjeta:
    """Cambia estado, asignación o rol de emergencia.

    `sucursal_id` se mueve porque el terminal de emergencia se presta: hoy
    cubre a CH1, la semana que viene a CH2.
    """
    pos = PosTarjetaRepo(session).get(pos_id)
    if pos is None:
        raise NoEncontrado("POS de tarjeta no encontrado")
    if estado is not None:
        if estado not in ESTADOS:
            raise Conflicto(f"estado de POS inválido: {estado}")
        pos.estado = estado
    if sucursal_id is not None:
        pos.sucursal_id = sucursal_id
    if es_emergencia is not None:
        pos.es_emergencia = es_emergencia
    return pos


def listar_pos(
    session: Session, empresa_id: uuid.UUID, sucursal_id: uuid.UUID | None = None
) -> list[PosTarjeta]:
    return PosTarjetaRepo(session).list(empresa_id, sucursal_id)
