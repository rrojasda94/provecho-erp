"""Contenido editable del sitio de marca (CMS mínimo, ADR-101).

Una fila por `(marca_id, clave)`. La forma de `valor` depende de la clave y
se valida en `application/contenido.py` con el modelo Pydantic
correspondiente (`api/schemas.py`) — el CHECK solo fija el vocabulario de
claves, no la forma del JSON.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin
from src.modules.storefront.domain.rules import CLAVES_CONTENIDO

_CLAVES_SQL = ", ".join(f"'{c}'" for c in CLAVES_CONTENIDO)


class StorefrontContenido(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "storefront_contenido"

    __table_args__ = (
        UniqueConstraint("marca_id", "clave"),
        CheckConstraint(
            f"clave IN ({_CLAVES_SQL})", name="clave_storefront_contenido"
        ),
    )

    marca_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("marca.id"), index=True)
    clave: Mapped[str] = mapped_column(String(40))
    valor: Mapped[dict] = mapped_column(JsonB)
    # Quién hizo el último `PUT`. Sin FK a `usuario` a propósito — mismo
    # criterio que `archivo.subido_por`: un UUID de auditoría, no una
    # relación que otro módulo tenga que mantener.
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
