"""Mixins comunes de modelo: PK UUID, timestamps, borrado lógico y ubicación.

Convenciones de docs/architecture/data-model.md: PK `id` (UUID),
`created_at`/`updated_at`, `deleted_at` donde aplique.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Integer, Numeric, String, Uuid, func
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


class UbicacionMixin:
    """Ancla una dirección de texto a un punto real del mapa (ADR-053).

    No reemplaza nada: el texto que se lee y se imprime sigue viviendo en la
    columna que cada tabla ya tenía (`direccion`, `domicilio`,
    `domicilio_fiscal`). Esto es lo que Google devuelve al elegir ese texto en
    el mapa, y es lo que permite medir una distancia de reparto o abrir la
    dirección en una app de navegación.

    Prefijo `ubicacion_` y no `direccion_` justamente porque la columna de
    texto no se llama igual en las cinco tablas que lo usan.

    **Todo nullable.** Una dirección escrita a mano es válida: en Tarapoto hay
    calles que Google no conoce, y el alta no puede depender de que un tercero
    conteste (mismo criterio que ADR-005).

    - `place_id` es el identificador estable del lugar en Google. Es lo que se
      compara para saber si dos pedidos van al mismo sitio.
    - `lat`/`lng` con 6 decimales: ~11 cm en el ecuador, de sobra para una
      puerta. Más decimales serían ruido del GPS.
    - `plus_code` se guarda aunque sea derivable de las coordenadas: viene
      gratis en la respuesta de Google y derivarlo pediría una dependencia.
    - `distrito` es lo que decide si una dirección cae en zona restringida
      para el reparto propio (ADR-054), sin traer geometría al proyecto.
    """

    ubicacion_place_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    ubicacion_lat: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6), nullable=True
    )
    ubicacion_lng: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6), nullable=True
    )
    ubicacion_plus_code: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    ubicacion_distrito: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
