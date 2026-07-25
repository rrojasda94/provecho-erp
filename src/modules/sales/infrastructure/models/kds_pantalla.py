"""Pantalla KDS: vista de cocina/despacho configurable por sucursal.

Cada pantalla filtra ítems por categorías de producto comercial
(`categoria_ids` JSONB; NULL = todas). El avance del pedido NO vive aquí:
vive en `venta_item.estado_preparacion` — todas las pantallas leen el
mismo estado, por eso se "comunican" entre sí sin infraestructura extra.

- tipo `preparacion`: estación de cocina — ve ítems pendientes/en curso
  de sus categorías y los avanza (bump).
- tipo `despacho`: pedidos listos — ve el pedido completo y su avance
  real; marca entrega.
"""

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, SoftDeleteMixin, TimestampMixin, UuidPkMixin


class KdsPantalla(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "kds_pantalla"
    __table_args__ = (UniqueConstraint("sucursal_id", "nombre"),)

    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    nombre: Mapped[str] = mapped_column(String(100))
    tipo: Mapped[str] = mapped_column(
        Enum("preparacion", "despacho", name="tipo_kds_pantalla", native_enum=False)
    )
    # Lista de categoria.id (str) que atiende; NULL/[] = todas.
    categoria_ids: Mapped[list | None] = mapped_column(JsonB, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
