"""Receta: BOM de un producto comercial o de una subreceta.

`producto_comercial.receta_id` la usa como BOM de venta directa;
`articulo_id` (aquí) la liga como BOM de una subreceta — cuando está
seteado, `production` la resuelve para saber qué consume una orden que
produce ese artículo (RN-PRD). Una receta sirve a uno u otro uso, no a
ambos a la vez.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Receta(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "receta"

    # La ficha técnica es de la empresa que la usa, no del grupo: dos
    # empresas del mismo grupo pueden vender la misma pizza con recetas
    # distintas, y una no tiene por qué ver la de la otra. Sin esta columna
    # el CRUD listaba todas y el hub replicaba todas (deuda cerrada
    # 2026-08-06).
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(150))
    rendimiento_cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    rendimiento_unidad_medida_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("unidad_medida.id")
    )
    flexible: Mapped[bool] = mapped_column(Boolean, default=False)
    # Solo si flexible=True, lo asigna Producción (RN-PRD-010).
    criterio_ajuste: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Subreceta que esta receta produce (tipo `subreceta` en `articulo`) —
    # nullable: NULL si la receta es de un producto_comercial de venta directa.
    articulo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("articulo.id"), nullable=True
    )
    # El `type` de `mrp.bom` en Odoo: `normal` (fabricar) vs `phantom` (Kit).
    #
    # False: `production` puede abrir una orden que la fabrique y guardar el
    # resultado como stock de `articulo_id`. Es la salsa que se prepara el
    # lunes para toda la semana.
    # True (kit): nunca se fabrica ni se stockea; se explota en el momento de
    # vender. Es la pizza mitad-y-mitad, que no existe hasta que alguien la
    # pide.
    #
    # Booleano y no un `tipo` de tres valores: Odoo tiene además
    # `subcontract` y acá nadie lo pidió — y `recetas.TIPOS_RECETA` ya
    # significa otra cosa (`subreceta` | `producto`, para filtrar el
    # listado). Dos columnas llamadas "tipo de receta" con ejes distintos es
    # cómo alguien filtra por una creyendo que filtra por la otra.
    #
    # Por defecto False: es lo que hacen todas las recetas de hoy y la
    # migración no puede cambiarle el comportamiento a ninguna.
    es_kit: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    # Identificador del sistema de origen ("__export__.mrp_bom_3001_871387aa").
    # Hace idempotente reimportar la misma planilla (ADR-057).
    ref_externa: Mapped[str | None] = mapped_column(
        String(120), nullable=True, unique=True
    )
