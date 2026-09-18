"""Favoritos de una cuenta (ADR-104). Valida el producto por el contrato
público de `sales`, nunca por su ORM."""

import uuid

from sqlalchemy.orm import Session

from src.modules.sales.application.queries_publicas import marca_de_producto
from src.modules.storefront.application.errors import Conflicto, NoEncontrado
from src.modules.storefront.infrastructure.models import StorefrontFavorito
from src.modules.storefront.infrastructure.repositories import FavoritoRepo


def listar(session: Session, cuenta_id: uuid.UUID) -> list[uuid.UUID]:
    return [f.producto_comercial_id for f in FavoritoRepo(session).listar(cuenta_id)]


def agregar(
    session: Session, *, cuenta_id: uuid.UUID, producto_comercial_id: uuid.UUID
) -> StorefrontFavorito:
    if marca_de_producto(session, producto_comercial_id) is None:
        raise NoEncontrado("producto no encontrado")
    repo = FavoritoRepo(session)
    if repo.get(cuenta_id, producto_comercial_id) is not None:
        raise Conflicto("ya está en favoritos")
    return repo.add(
        StorefrontFavorito(cuenta_id=cuenta_id, producto_comercial_id=producto_comercial_id)
    )


def quitar(
    session: Session, *, cuenta_id: uuid.UUID, producto_comercial_id: uuid.UUID
) -> None:
    repo = FavoritoRepo(session)
    favorito = repo.get(cuenta_id, producto_comercial_id)
    if favorito is None:
        raise NoEncontrado("no estaba en favoritos")
    repo.borrar(favorito)
