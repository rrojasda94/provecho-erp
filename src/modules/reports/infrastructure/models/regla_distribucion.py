"""Regla de distribución: qué emisión se reparte, dónde y con qué urgencia.

Es la tabla que este módulo existe para tener. Antes, «quién recibe qué»
vivía en dos funciones de Python (`users.application.notificaciones`), así
que cambiarlo era un deploy y verlo era leer código.

`codigo_emision` **no es FK**: el catálogo de emisiones es una lista cerrada
en código (`domain/catalogo.py`), no una tabla. Se valida al guardar contra
`catalogo.obtener()` — una regla nunca puede referirse a una emisión que no
existe (RN-REP-001).
"""

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class ReglaDistribucion(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "regla_distribucion"
    __table_args__ = (
        # Una regla por (empresa, emisión, sucursal) — RN-REP-008. Son dos
        # índices parciales y no un `UniqueConstraint` de tres columnas
        # porque en SQL los NULL son distintos entre sí: con la constraint
        # simple, dos reglas generales de la misma emisión (ambas con
        # `sucursal_id` nulo) convivirían y el hecho se entregaría dos veces.
        Index(
            "uq_regla_por_sucursal",
            "empresa_id",
            "codigo_emision",
            "sucursal_id",
            unique=True,
            sqlite_where=text("sucursal_id IS NOT NULL"),
            postgresql_where=text("sucursal_id IS NOT NULL"),
        ),
        Index(
            "uq_regla_general",
            "empresa_id",
            "codigo_emision",
            unique=True,
            sqlite_where=text("sucursal_id IS NULL"),
            postgresql_where=text("sucursal_id IS NULL"),
        ),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    codigo_emision: Mapped[str] = mapped_column(String(60), index=True)
    # Nulo = la regla general de la empresa. Solo aplica donde no hay una
    # específica de esa sucursal (`domain.rules.elegir_regla`).
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )
    # Desactivar en vez de borrar: el histórico de `reporte_emitido` apunta a
    # la regla que lo produjo, y borrarla dejaría reportes sin explicación de
    # por qué llegaron a quien llegaron.
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    # Pisa el nivel por defecto de la emisión: el mismo hecho interrumpe
    # distinto según la empresa (un descuadre de S/ 5 no es urgente en todos
    # lados).
    nivel: Mapped[str] = mapped_column(
        Enum("info", "aviso", "urgente", name="nivel_regla", native_enum=False),
        default="aviso",
    )
    canal: Mapped[str] = mapped_column(
        Enum("bandeja", name="canal_regla", native_enum=False), default="bandeja"
    )
