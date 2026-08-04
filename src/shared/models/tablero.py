"""Tablero: la disposición de tarjetas de reporte que un usuario guardó.

Es preferencia de presentación, no dato de negocio: qué reportes mira, en
qué orden, de qué tamaño y con qué filtros por defecto. Vive en `shared` por
lo mismo que el router de reportes vive en `core` — compone reportes de
varios módulos y no le pertenece a ninguno.

`tarjetas` y `filtros` son JSON a propósito: la forma de una tarjeta cambia
cada vez que se agrega un tipo de visualización, y normalizarla obligaría a
una migración por cada una. Lo que **no** es libre es el `codigo` de reporte
que cada tarjeta nombra: se valida contra el catálogo (`core/reportes`) al
guardar, así que un tablero nunca puede referirse a un reporte inexistente
ni a uno para el que el usuario no tiene permiso.
"""

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class Tablero(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "tablero"
    __table_args__ = (
        # Un solo tablero predeterminado por usuario — el que abre el
        # dashboard sin que él elija nada.
        Index(
            "uq_tablero_predeterminado",
            "usuario_id",
            unique=True,
            sqlite_where=text("predeterminado = 1"),
            postgresql_where=text("predeterminado"),
        ),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    # Dueño: el único que puede editarlo o borrarlo, aunque esté compartido.
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    # NULL = privado. Con rol, lo ve (solo lectura) cualquiera que tenga ese
    # rol. Se comparte por rol y no con una lista de personas porque así se
    # administra solo: alguien cambia de puesto y gana o pierde el tablero
    # sin que nadie recuerde actualizar una lista — y un trabajador que cesa
    # deja de verlo al perder el rol, no al ser removido a mano de cada uno.
    #
    # Compartir no expone datos: cada reporte del tablero sigue exigiendo el
    # permiso de su módulo dueño al pedir sus datos. Lo que se comparte es
    # la *disposición*, no el contenido — quien no tenga `purchases.leer`
    # abre el tablero compartido y esa tarjeta le responde 403.
    rol_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rol.id"), nullable=True, index=True
    )
    nombre: Mapped[str] = mapped_column(String(100))
    predeterminado: Mapped[bool] = mapped_column(Boolean, default=False)
    # [{"codigo": "ventas_por_dia", "visual": "lineas", "ancho": 2,
    #   "alto": "mediano", "titulo": "Tendencia"}]
    tarjetas: Mapped[list[Any]] = mapped_column(JsonB, default=list)
    # {"preset": "mes_actual", "desde": null, "hasta": null,
    #  "sucursal_ids": ["..."]}
    filtros: Mapped[dict[str, Any]] = mapped_column(JsonB, default=dict)
