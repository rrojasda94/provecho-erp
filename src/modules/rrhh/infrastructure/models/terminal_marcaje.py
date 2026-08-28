"""Terminal de marcaje: el dispositivo autorizado a marcar por una sucursal.

La cuenta de servicio del pad (`terminal_asistencia`, ADR-065) resuelve
*quién puede abrir* la pantalla; esto resuelve *desde dónde*. Sin esto, la
sesión de la tablet es exportable: con el mismo token, `/asistencia`
funciona igual de bien desde cualquier navegador — el celular de un
supervisor que quiere marcar sin haber llegado, por ejemplo.

Enrolamiento en dos pasos, ninguno técnico: un admin crea el registro desde
el back-office (nace `activo=False` con un código de 6 dígitos, vigente 30
minutos) y la tablet lo teclea una vez en el pad. El servidor guarda solo el
hash del secreto que la tablet genera — el valor en claro no vuelve a
existir del lado del servidor, igual que `TokenAgente`.

SHA-256 y no Argon2id a propósito: el secreto son 128 bits que genera el
servidor, no una contraseña humana — no hay diccionario que atacar.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class TerminalMarcaje(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "terminal_marcaje"
    __table_args__ = (
        # Único entre los vivos, no entre todos: un terminal borrado libera
        # su nombre para otra tablet (mismo patrón que `kds_pantalla`).
        Index(
            "uq_terminal_marcaje_vivo",
            "sucursal_id",
            "nombre",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_terminal_marcaje_secreto",
            "secreto_hash",
            unique=True,
            sqlite_where=text("secreto_hash IS NOT NULL"),
            postgresql_where=text("secreto_hash IS NOT NULL"),
        ),
    )

    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    nombre: Mapped[str] = mapped_column(String(80))
    # El código de activación y su vencimiento se borran al enrolar: no hay
    # motivo para conservar un código que ya cumplió su función, y uno vivo
    # es una ventana de ataque mientras exista.
    codigo: Mapped[str | None] = mapped_column(String(6), nullable=True)
    codigo_expira_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    secreto_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=False)
    # Para distinguir un terminal enrolado de uno abandonado sin volver a
    # marcar — no dispara nada, es lectura para el back-office.
    ultima_marcacion_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
