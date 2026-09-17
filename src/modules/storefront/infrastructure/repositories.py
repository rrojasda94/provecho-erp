"""Repositorios de `storefront`."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.storefront.infrastructure.models import StorefrontContenido


class ContenidoRepo:
    def __init__(self, session: Session):
        self.session = session

    def get(self, marca_id: uuid.UUID, clave: str) -> StorefrontContenido | None:
        return self.session.scalar(
            select(StorefrontContenido).where(
                StorefrontContenido.marca_id == marca_id,
                StorefrontContenido.clave == clave,
            )
        )

    def listar(self, marca_id: uuid.UUID) -> list[StorefrontContenido]:
        return list(
            self.session.scalars(
                select(StorefrontContenido).where(
                    StorefrontContenido.marca_id == marca_id
                )
            )
        )

    def add(self, contenido: StorefrontContenido) -> StorefrontContenido:
        self.session.add(contenido)
        self.session.flush()
        return contenido
