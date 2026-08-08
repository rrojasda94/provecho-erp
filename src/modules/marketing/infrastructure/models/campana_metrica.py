"""Acumulado de una campaña, mantenido por los listeners de marketing.

Existe porque los eventos de marketing (`campana_lanzada`, `lead_generado`,
`lead_atribuido`, `pieza_publicada`) no tenían **ningún** consumidor: se
publicaban y se perdían. Ahora el propio módulo los escucha y los acumula
acá, y BI lee una fila en vez de reconstruir la historia contando tablas.

Es un acumulado derivado: si se corrompe se puede reconstruir desde `lead`,
`pieza_contenido` y `encuesta_satisfaccion`. No es fuente de verdad de nada.

La parte de satisfacción se acredita por la cadena lead → venta → encuesta:
solo cuenta la encuesta de una venta que un lead de esta campaña atribuyó.
Es la única forma de contestar "¿la gente que trajo esta campaña quedó
contenta?" sin inventar una relación campaña-encuesta que no existe.
"""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class CampanaMetrica(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "campana_metrica"

    campana_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campana.id"), unique=True)
    fecha_lanzamiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    leads_generados: Mapped[int] = mapped_column(Integer, default=0)
    leads_convertidos: Mapped[int] = mapped_column(Integer, default=0)
    piezas_publicadas: Mapped[int] = mapped_column(Integer, default=0)
    encuestas_enviadas: Mapped[int] = mapped_column(Integer, default=0)
    encuestas_respondidas: Mapped[int] = mapped_column(Integer, default=0)
    # Suma, no promedio: promediar promedios da un número que no es de nadie.
    puntaje_suma: Mapped[int] = mapped_column(Integer, default=0)
