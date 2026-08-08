"""token_agente: credencial de larga vida de una cuenta `agente_ia`.

Un agente (n8n, el bot de pedidos, un script de integración) no tiene
teclado: pedirle un PIN de 6 dígitos y rotarle un refresh cada 7 días es
ceremonia humana aplicada a una máquina. El token es una cadena aleatoria
larga, se guarda solo su SHA-256 (nunca el valor en claro, igual que
`refresh_token`) y el `prefijo` existe para poder decir *cuál* token
revocar sin conocer ninguno.

No reemplaza al RBAC: el token identifica al usuario y de ahí salen sus
roles, permisos y sucursales como en cualquier login.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class TokenAgente(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "token_agente"

    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    # Para qué es este token ("n8n producción", "bot de pedidos WhatsApp").
    nombre: Mapped[str] = mapped_column(String(100))
    # Primeros caracteres del token en claro: lo único que puede mostrarse
    # después de crearlo.
    prefijo: Mapped[str] = mapped_column(String(16), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # NULL = sin vencimiento. Una integración que corre sola no puede
    # quedarse tirada un domingo porque venció un token, pero un token de
    # prueba sí conviene que muera solo.
    expira_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revocado: Mapped[bool] = mapped_column(Boolean, default=False)
    # Para poder apagar lo que ya nadie usa sin adivinar.
    ultimo_uso_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
