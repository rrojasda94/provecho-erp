"""Cuenta de cliente del sitio de marca (ADR-102).

Credencial **completamente separada** de `usuario` (staff del ERP): secreto
de JWT propio, sin PIN, sin rol/permiso. `cliente_id` es el enlace hacia el
padrón comercial de `sales` — se completa por evento
(`storefront.cuenta_registrada` → `sales.cliente_vinculado`), nunca por un
import directo a `sales.application.clientes` (contrato entre módulos).

Reemplaza, para el caso de autoservicio web, la idea original de
`cliente.usuario_id` (ver su docstring): esa columna suponía una cuenta de
`usuario` del ERP para el cliente, y `usuario` es la tabla de credenciales
del personal. `storefront_cuenta` es la que en verdad separa las dos
identidades — `cliente.usuario_id` queda sin usar para este caso.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class StorefrontCuenta(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "storefront_cuenta"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # NULL si la cuenta se creó solo con Google (nunca tecleó una clave acá).
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # `sub` del token de Google — identifica a la cuenta de Google, no
    # cambia aunque la persona cambie de email. NULL si nunca vinculó Google.
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    nombres: Mapped[str] = mapped_column(String(150))
    apellidos: Mapped[str] = mapped_column(String(150))
    tipo_documento: Mapped[str | None] = mapped_column(String(10), nullable=True)
    numero_documento: Mapped[str | None] = mapped_column(String(15), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date(), nullable=True)

    # NULL hasta que el listener de `sales` responda (best-effort, ADR-016);
    # una tarea de reconciliación cubre el caso en que el evento se pierda.
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cliente.id"), nullable=True, unique=True
    )

    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
