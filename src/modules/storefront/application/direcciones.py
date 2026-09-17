"""Direcciones de envío de una cuenta (ADR-102): varias, nombrables, una
predeterminada. El cliente elige cuál usar en cada pedido (F3) — acá solo
se guardan."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.modules.storefront.application.errors import NoEncontrado
from src.modules.storefront.infrastructure.models import StorefrontDireccion
from src.modules.storefront.infrastructure.repositories import DireccionRepo


def listar(session: Session, cuenta_id: uuid.UUID) -> list[StorefrontDireccion]:
    return DireccionRepo(session).listar(cuenta_id)


def _quitar_predeterminada_actual(session: Session, cuenta_id: uuid.UUID) -> None:
    for d in DireccionRepo(session).listar(cuenta_id):
        d.predeterminada = False


def crear(
    session: Session,
    *,
    cuenta_id: uuid.UUID,
    etiqueta: str | None,
    direccion: str,
    referencia: str | None,
    predeterminada: bool,
    ubicacion: dict | None = None,
) -> StorefrontDireccion:
    if predeterminada:
        _quitar_predeterminada_actual(session, cuenta_id)
    # La primera dirección de la cuenta es predeterminada aunque no se pida:
    # sin ninguna marcada, el checkout de F3 no tendría cuál preseleccionar.
    ya_tiene_alguna = bool(DireccionRepo(session).listar(cuenta_id))
    return DireccionRepo(session).add(
        StorefrontDireccion(
            cuenta_id=cuenta_id, etiqueta=etiqueta, direccion=direccion,
            referencia=referencia, predeterminada=predeterminada or not ya_tiene_alguna,
            **(ubicacion or {}),
        )
    )


def _exigir_propia(
    session: Session, cuenta_id: uuid.UUID, direccion_id: uuid.UUID
) -> StorefrontDireccion:
    d = DireccionRepo(session).get(direccion_id)
    if d is None or d.cuenta_id != cuenta_id:
        # Mismo mensaje si es de otra cuenta o no existe: no se le confirma
        # a nadie que un id ajeno es válido.
        raise NoEncontrado("dirección no encontrada")
    return d


def editar(
    session: Session,
    *,
    cuenta_id: uuid.UUID,
    direccion_id: uuid.UUID,
    etiqueta: str | None = None,
    direccion: str | None = None,
    referencia: str | None = None,
    predeterminada: bool | None = None,
    ubicacion: dict | None = None,
) -> StorefrontDireccion:
    d = _exigir_propia(session, cuenta_id, direccion_id)
    if etiqueta is not None:
        d.etiqueta = etiqueta
    if direccion is not None:
        d.direccion = direccion
    if referencia is not None:
        d.referencia = referencia
    if predeterminada:
        _quitar_predeterminada_actual(session, cuenta_id)
        d.predeterminada = True
    for campo, valor in (ubicacion or {}).items():
        setattr(d, campo, valor)
    return d


def borrar(session: Session, *, cuenta_id: uuid.UUID, direccion_id: uuid.UUID) -> None:
    d = _exigir_propia(session, cuenta_id, direccion_id)
    d.deleted_at = datetime.now(UTC)
