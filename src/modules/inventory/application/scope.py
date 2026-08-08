"""Validación de alcance de tenant sobre recursos de inventory (ADR-004).

El `empresa_id` nunca viene del cliente: se deriva del JWT y aquí se
contrasta contra el recurso que el request dice tocar.
"""

import uuid

from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.inventory.application.errors import NoEncontrado
from src.modules.inventory.infrastructure.models import (
    Ajuste,
    Articulo,
    Categoria,
    Conteo,
    Devolucion,
    Lote,
    Receta,
    ReservaStock,
    SolicitudInsumos,
    Transferencia,
)
from src.modules.users.infrastructure.models import Almacen


def exigir_almacen(session: Session, almacen_id: uuid.UUID, tenant: Tenant) -> Almacen:
    almacen = session.get(Almacen, almacen_id)
    if almacen is None or almacen.deleted_at is not None:
        raise NoEncontrado("almacén no encontrado")
    tenant.exigir_empresa(almacen.empresa_id)
    return almacen


def exigir_articulo(
    session: Session, articulo_id: uuid.UUID, tenant: Tenant
) -> Articulo:
    articulo = session.get(Articulo, articulo_id)
    if articulo is None or articulo.deleted_at is not None:
        raise NoEncontrado("artículo no encontrado")
    tenant.exigir_empresa(articulo.empresa_id)
    return articulo


def exigir_lote(session: Session, lote_id: uuid.UUID, tenant: Tenant) -> Lote:
    lote = session.get(Lote, lote_id)
    if lote is None:
        raise NoEncontrado("lote no encontrado")
    exigir_articulo(session, lote.articulo_id, tenant)
    return lote


def exigir_categoria(
    session: Session, categoria_id: uuid.UUID, tenant: Tenant
) -> Categoria:
    categoria = session.get(Categoria, categoria_id)
    if categoria is None or categoria.deleted_at is not None:
        raise NoEncontrado("categoría no encontrada")
    tenant.exigir_empresa(categoria.empresa_id)
    return categoria


def exigir_devolucion(
    session: Session, devolucion_id: uuid.UUID, tenant: Tenant
) -> Devolucion:
    devolucion = session.get(Devolucion, devolucion_id)
    if devolucion is None:
        raise NoEncontrado("devolución no encontrada")
    exigir_almacen(session, devolucion.almacen_id, tenant)
    return devolucion


def exigir_receta(session: Session, receta_id: uuid.UUID, tenant: Tenant) -> Receta:
    receta = session.get(Receta, receta_id)
    if receta is None:
        raise NoEncontrado("receta no encontrada")
    tenant.exigir_empresa(receta.empresa_id)
    return receta


def exigir_conteo(session: Session, conteo_id: uuid.UUID, tenant: Tenant) -> Conteo:
    conteo = session.get(Conteo, conteo_id)
    if conteo is None:
        raise NoEncontrado("conteo no encontrado")
    exigir_almacen(session, conteo.almacen_id, tenant)
    return conteo


def exigir_solicitud(
    session: Session, solicitud_id: uuid.UUID, tenant: Tenant
) -> SolicitudInsumos:
    solicitud = session.get(SolicitudInsumos, solicitud_id)
    if solicitud is None:
        raise NoEncontrado("solicitud no encontrada")
    exigir_almacen(session, solicitud.almacen_solicitante_id, tenant)
    return solicitud


def exigir_transferencia(
    session: Session, transferencia_id: uuid.UUID, tenant: Tenant
) -> Transferencia:
    transferencia = session.get(Transferencia, transferencia_id)
    if transferencia is None:
        raise NoEncontrado("transferencia no encontrada")
    exigir_almacen(session, transferencia.origen_almacen_id, tenant)
    return transferencia


def exigir_reserva(
    session: Session, reserva_id: uuid.UUID, tenant: Tenant
) -> ReservaStock:
    reserva = session.get(ReservaStock, reserva_id)
    if reserva is None:
        raise NoEncontrado("reserva no encontrada")
    exigir_almacen(session, reserva.almacen_id, tenant)
    return reserva


def exigir_ajuste(session: Session, ajuste_id: uuid.UUID, tenant: Tenant) -> Ajuste:
    ajuste = session.get(Ajuste, ajuste_id)
    if ajuste is None:
        raise NoEncontrado("ajuste no encontrado")
    exigir_almacen(session, ajuste.almacen_id, tenant)
    return ajuste
