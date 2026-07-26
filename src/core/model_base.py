"""Mixins comunes de modelo: PK UUID, timestamps y borrado lógico.

Convenciones de docs/architecture/data-model.md: PK `id` (UUID),
`created_at`/`updated_at`, `deleted_at` donde aplique.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

# JSONB en Postgres, JSON genérico en otros dialectos (tests con SQLite).
JsonB = JSON().with_variant(JSONB(), "postgresql")


class UuidPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class VersionedMixin:
    """Lock optimista a nivel de aplicación (no `version_id_col` de SQLAlchemy,
    que exige `__mapper_args__` por clase concreta). El repositorio hace un
    UPDATE condicional `WHERE version = :esperada` — atómico, sin ventana de
    carrera entre leer y escribir."""

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
