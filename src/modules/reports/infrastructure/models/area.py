"""Área: el destinatario colectivo de un reporte.

El ERP ya nombraba áreas antes de tener esta tabla —
`inventory.conteo_vencido` publica `dirigido_a: ["almacen", "gerencia"]` y
`devolucion.reporte_dirigido_a` guarda `almacen`|`comercial`— pero eran
cadenas que nadie podía resolver a una persona. Acá es donde `almacen` deja
de ser texto y pasa a ser gente.

**No es un rol.** Un rol dice qué puede hacer alguien; un área dice de qué se
tiene que enterar. Se parecen tanto que la tentación es fusionarlos, y no
coinciden: `gerencia`, `comercial` y `almacen` no son roles del RBAC hoy, y
un área se compone de varios roles más personas puntuales.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Area(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "area"
    __table_args__ = (
        UniqueConstraint("empresa_id", "codigo", name="uq_area_empresa_codigo"),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    # `almacen`, `gerencia`, `comercial`… Es el que aparece en los payloads
    # que el ERP ya publica, así que el seeder crea los de `AREAS_BASE` con
    # exactamente esos códigos.
    codigo: Mapped[str] = mapped_column(String(30))
    nombre: Mapped[str] = mapped_column(String(100))
    # Desactivar en vez de borrar: un área con reglas colgando no se puede
    # borrar sin dejar huérfanas las reglas, y borrarlas en cascada sería
    # perder el gobierno por un clic.
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
