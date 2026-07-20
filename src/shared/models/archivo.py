"""Archivo: vínculo polimórfico de archivos (S3) a cualquier entidad.

Generado por el ERP (plantillas) o subido por el usuario (RN-ARC-001/002).
`plantilla_id` y `subido_por` quedan como UUID sin FK hasta que existan
las tablas `plantilla` y `usuario` (slices posteriores).
"""

import uuid

from sqlalchemy import BigInteger, Enum, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Archivo(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "archivo"

    nombre: Mapped[str] = mapped_column(String(255))
    extension: Mapped[str] = mapped_column(String(10))
    mime_type: Mapped[str] = mapped_column(String(100))
    tamano_bytes: Mapped[int] = mapped_column(BigInteger)
    url_storage: Mapped[str] = mapped_column(String(500))
    origen: Mapped[str] = mapped_column(
        Enum("generado", "subido", name="origen_archivo", native_enum=False)
    )
    # Vínculo polimórfico: nombre de tabla + id de la fila vinculada.
    entidad_tipo: Mapped[str] = mapped_column(String(50), index=True)
    entidad_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    plantilla_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    subido_por: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
