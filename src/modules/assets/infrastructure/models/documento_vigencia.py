"""Documento con fecha de vencimiento: permiso, certificado o licencia de un
activo, sucursal, empresa o trabajador (pedido del usuario 2026-09-09 — no
tenía ninguna entidad en el ERP).

Polimórfico y sin FK a propósito, mismo patrón que `notificacion` y
`decision_gerencial`: los cuatro tipos de sujeto viven en tres módulos
distintos (`assets`, `users`, `rrhh`) y una FK real solo podría apuntar a
uno.
"""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin
from src.modules.assets.domain.rules import (
    DIAS_AVISO_DOCUMENTO_DEFECTO,
    SUJETOS_DOCUMENTO,
    TIPOS_DOCUMENTO,
)


class DocumentoVigencia(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "documento_vigencia"

    __table_args__ = (
        CheckConstraint(
            "sujeto_tipo IN ('activo', 'sucursal', 'empresa', 'trabajador')",
            name="sujeto_documento_vigencia",
        ),
        CheckConstraint(
            "tipo_documento IN ("
            "'soat', 'revision_tecnica', 'tarjeta_propiedad', 'poliza_seguro', "
            "'garantia', 'licencia_funcionamiento', 'certificado_defensa_civil', "
            "'fumigacion', 'registro_sanitario', 'carne_sanidad', "
            "'licencia_conducir', 'otro')",
            name="tipo_documento_vigencia",
        ),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    sujeto_tipo: Mapped[str] = mapped_column(
        Enum(*SUJETOS_DOCUMENTO, name="sujeto_documento_vigencia", native_enum=False)
    )
    # Sin FK: según `sujeto_tipo` apunta a `activo` (este módulo), `sucursal`/
    # `empresa` (`users`) o `trabajador` (`rrhh`) — cuatro tablas de tres
    # módulos distintos, ninguna FK cubre las cuatro. Se valida por
    # `application/scope.py` según el tipo.
    sujeto_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    tipo_documento: Mapped[str] = mapped_column(
        Enum(*TIPOS_DOCUMENTO, name="tipo_documento_vigencia", native_enum=False)
    )
    numero: Mapped[str | None] = mapped_column(String(60), nullable=True)
    emisor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    fecha_emision: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_vencimiento: Mapped[date] = mapped_column(Date)
    dias_aviso: Mapped[int] = mapped_column(default=DIAS_AVISO_DOCUMENTO_DEFECTO)
    # El documento que lo reemplazó — encadena la vigencia sin borrar el
    # historial (una inspección puede pedir ver el SOAT vencido de hace un
    # año). Auto-FK.
    renovado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documento_vigencia.id"), nullable=True
    )
    aviso_proximo_en: Mapped[date | None] = mapped_column(Date, nullable=True)
    aviso_vencido_en: Mapped[date | None] = mapped_column(Date, nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
