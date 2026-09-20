"""Favoritos de una cuenta (ADR-104). Valida el producto por el contrato
público de `sales`, nunca por su ORM."""

import uuid

from sqlalchemy.orm import Session

from src.modules.sales.application.queries_publicas import marca_de_producto
from src.modules.storefront.application.errors import NoEncontrado
from src.modules.storefront.infrastructure.models import StorefrontFavorito
from src.modules.storefront.infrastructure.repositories import FavoritoRepo


def listar(session: Session, cuenta_id: uuid.UUID) -> list[uuid.UUID]:
    return [f.producto_comercial_id for f in FavoritoRepo(session).listar(cuenta_id)]


def agregar(
    session: Session, *, cuenta_id: uuid.UUID, producto_comercial_id: uuid.UUID
) -> StorefrontFavorito:
    """Idempotente: marcar dos veces deja el producto marcado, no falla.

    Antes devolvía 409 si ya estaba y 404 al quitar algo que no estaba. Un
    corazón en una tarjeta no es una operación transaccional: basta con que la
    lista del cliente y la del servidor queden desincronizadas un instante
    (token vencido, lista que no cargó) para que el siguiente toque mande el
    verbo contrario, lo rechacen y el corazón quede trabado. El estado final es
    lo único que importa acá.
    """
    if marca_de_producto(session, producto_comercial_id) is None:
        raise NoEncontrado("producto no encontrado")
    repo = FavoritoRepo(session)
    existente = repo.get(cuenta_id, producto_comercial_id)
    if existente is not None:
        return existente
    return repo.add(
        StorefrontFavorito(cuenta_id=cuenta_id, producto_comercial_id=producto_comercial_id)
    )


def quitar(session: Session, *, cuenta_id: uuid.UUID, producto_comercial_id: uuid.UUID) -> None:
    """Idempotente, mismo criterio que `agregar`: quitar lo que no estaba no
    es un error, el producto ya no es favorito."""
    repo = FavoritoRepo(session)
    favorito = repo.get(cuenta_id, producto_comercial_id)
    if favorito is not None:
        repo.borrar(favorito)
