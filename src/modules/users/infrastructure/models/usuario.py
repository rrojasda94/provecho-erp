"""Usuario: identidad que se autentica. Tipo humano (liga a persona) o
agente_ia (sin persona).

Alcance mínimo para este slice — RBAC completo (rol, permiso,
usuario_rol, rol_permiso, refresh_token, audit_log) se modela en el
slice dedicado de auth (data-model.md §2).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Usuario(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "usuario"
    __table_args__ = (
        # Única entre las vivas: una persona tiene a lo más una cuenta con
        # PIN. Es la arista de la que cuelga el pad de asistencia
        # (`rrhh.trabajador.usuario_id` se deriva de esta columna, RN-RRHH-020,
        # ADR-070) — sin la unicidad, dos cuentas sobre la misma persona
        # dejarían al pad sin saber cuál firma.
        Index(
            "uq_usuario_persona_viva",
            "persona_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    username: Mapped[str] = mapped_column(String(50), unique=True)
    pin_hash: Mapped[str] = mapped_column(String(255))
    # NULL si tipo=agente_ia. Única arista cuenta<->trabajador (ADR-070): el
    # trabajador marca en el pad con el PIN de la cuenta cuya persona_id es
    # la suya. `lazy` por defecto (no `joined`): cargar la persona en cada
    # lectura de Usuario metería un LEFT JOIN en el camino más caliente del
    # ERP (login, `require_permission`, el exportador del hub).
    persona_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("persona.id"), nullable=True
    )
    persona: Mapped["Persona | None"] = relationship()  # noqa: F821
    # Fallback de nombre para agente_ia (sin persona).
    nombre_display: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tipo: Mapped[str] = mapped_column(
        Enum("humano", "agente_ia", name="tipo_usuario", native_enum=False)
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # El PIN vigente lo puso otra persona (un reseteo), así que es conocido
    # por alguien más y no sirve para responder por lo que se haga con esta
    # cuenta. Mientras esté en `True`, `get_current_user` deja pasar solo lo
    # necesario para cambiarlo: sin eso, "cambio obligatorio" sería un cartel
    # que se cierra con la X.
    debe_cambiar_pin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    # Lockout: 5 intentos fallidos en ventana de 15 min bloquean el login.
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Preferencias de presentación. Viven en el usuario y no en el navegador
    # (docs/product/ui-ux.md): en un local la misma tablet la usan tres turnos
    # distintos y la misma persona pasa de la caja a la oficina. Guardarlas en
    # el dispositivo obligaría a reconfigurarlas en cada máquina, que en la
    # práctica significa no usarlas.
    #
    # `alto_contraste` no es "otro tema": es la paleta de estados alternativa
    # para daltonismo rojo-verde. `tema` es preferencia de entorno (la luz de
    # la sala: la oficina y la cocina a las 6 a.m. no son lo mismo).
    #
    # Sin opción "seguir al sistema": detectarla exige leer `prefers-color-
    # scheme` en el navegador, y hacerlo antes del primer pintado pide un
    # script inline que la CSP de `middleware.ts` firma con nonce por request.
    # Abrirle una excepción al único control que frena XSS, para ahorrar un
    # clic en una preferencia que ya viaja con la persona entre máquinas, no
    # es un intercambio que convenga.
    preferencia_paleta: Mapped[str] = mapped_column(
        Enum("estandar", "alto_contraste", name="preferencia_paleta", native_enum=False),
        default="estandar",
        server_default="estandar",
    )
    preferencia_tamano_fuente: Mapped[str] = mapped_column(
        Enum(
            "estandar",
            "grande",
            "muy_grande",
            "maximo",
            name="preferencia_tamano_fuente",
            native_enum=False,
        ),
        default="estandar",
        server_default="estandar",
    )
    preferencia_tema: Mapped[str] = mapped_column(
        Enum("claro", "oscuro", name="preferencia_tema", native_enum=False),
        default="claro",
        server_default="claro",
    )
