"""Pantalla KDS: vista de cocina/despacho configurable por sucursal.

Cada pantalla filtra ítems por categorías de producto comercial
(`categoria_ids` JSONB; NULL = todas). El avance del pedido NO vive aquí:
vive en `venta_item.estado_preparacion` — todas las pantallas leen el
mismo estado, por eso se "comunican" entre sí sin infraestructura extra.

- tipo `preparacion`: estación de cocina — ve ítems pendientes/en curso
  de sus categorías y los avanza (bump).
- tipo `despacho`: pedidos listos — ve el pedido completo y su avance
  real; marca entrega.

Las estaciones de preparación forman una CADENA por `orden` (armado →
horno → …): una línea la ve la primera estación con `orden >= su
etapa_kds` que atienda su categoría, y marcarla la manda a la siguiente
(ADR-044). Despacho no está en la cadena — mira `estado_preparacion`, que
es donde cae la línea cuando ya no queda estación por delante.
"""

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, SoftDeleteMixin, TimestampMixin, UuidPkMixin


class KdsPantalla(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "kds_pantalla"
    __table_args__ = (
        # Único entre las vivas, no entre todas: una estación borrada
        # (`deleted_at`) libera su nombre. Con un UNIQUE plano, borrar
        # «Horno» por un error de tipeo dejaba el nombre ocupado para
        # siempre — mismo patrón que `parametro_empresa`.
        Index(
            "uq_kds_pantalla_viva",
            "sucursal_id",
            "nombre",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    nombre: Mapped[str] = mapped_column(String(100))
    tipo: Mapped[str] = mapped_column(
        Enum("preparacion", "despacho", name="tipo_kds_pantalla", native_enum=False)
    )
    # Lista de categoria.id (str) que atiende; NULL/[] = todas.
    categoria_ids: Mapped[list | None] = mapped_column(JsonB, nullable=True)
    # Eslabón de la cadena de preparación. Todo empieza en 0: una cocina de
    # una sola estación es una cadena de un eslabón, y por eso la columna
    # nace con default 0 y no rompe ninguna sucursal ya configurada.
    # Dos estaciones con el mismo `orden` son el mismo eslabón (horno y
    # barra trabajando en paralelo, cada una con sus categorías).
    orden: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
