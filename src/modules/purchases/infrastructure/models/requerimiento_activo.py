"""requerimiento_activo: qué activo se está comprando en una OC tipo
`activo` — nombre, categoría y el costo estimado que se vuelve
`valor_compra` del activo al recibir (ADR-098).

Una OC de este tipo compra **un** activo (no un lote de N unidades): cada
fila de este slice necesita su propio `id_interno` en `assets`, y
generarlos en serie es la misma deuda de siempre (RN-GEN-005, nadie los
autogenera). Comprar varias unidades del mismo activo en una sola OC queda
declarado como deuda.

Sin la doble aprobación de área/gerencia ni las cotizaciones mínimas que
`docs/contabilidad/README.md` (PROC-CTB-010) describe para el proceso
completo: la aprobación de esta OC es la misma de cualquier otra —umbral +
`purchases.aprobar`— y las cotizaciones no se modelan todavía. Deuda
declarada, no un olvido.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class RequerimientoActivo(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "requerimiento_activo"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    # A qué sucursal va (RN-GEN-005 lo pide corregible por pantalla, igual
    # que `assets.Activo.sucursal_id`). Nula = administración/central.
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sucursal.id"), nullable=True)
    # El futuro `activo.id_interno` — se tecleó acá, no se autogenera
    # (mismo criterio que `assets.crear_activo`).
    id_interno: Mapped[str] = mapped_column(String(8))
    nombre: Mapped[str] = mapped_column(String(150))
    categoria: Mapped[str | None] = mapped_column(String(60), nullable=True)
    marca: Mapped[str | None] = mapped_column(String(60), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    costo_estimado: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Para que `accounting` pueda empezar a depreciarlo apenas nace el
    # activo — opcional, igual que en `assets.Activo`.
    vida_util_meses: Mapped[int | None] = mapped_column(nullable=True)
    solicitado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
