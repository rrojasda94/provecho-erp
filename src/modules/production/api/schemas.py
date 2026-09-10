"""DTOs (pydantic) del módulo production."""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrdenProduccionCreate(BaseModel):
    articulo_id: uuid.UUID
    almacen_id: uuid.UUID
    cantidad_planeada: Decimal = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=100)


class OrdenProduccionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    articulo_id: uuid.UUID
    almacen_id: uuid.UUID
    cantidad_planeada: Decimal
    cantidad_producida: Decimal | None
    estado: str
    costo_insumos: Decimal | None
    costo_mano_obra: Decimal | None
    costo_real_unitario: Decimal | None
    merma_cantidad: Decimal | None
    merma_motivo: str | None
    fecha_vencimiento: date | None
    lote_codigo: str | None
    trazabilidad: dict | None


class ConsumoItemIn(BaseModel):
    articulo_id: uuid.UUID
    cantidad: Decimal = Field(gt=0)
    costo_unitario: Decimal = Field(ge=0)
    peso_desperdicio_real: Decimal = Decimal(0)
    tipo_desperdicio: str | None = None


class ConsumoCreate(BaseModel):
    items: list[ConsumoItemIn] = Field(min_length=1)
    # Opcional: sin ella, un reintento de red puede duplicar el consumo
    # (deuda técnica, ver ROADMAP). Con la misma clave, la segunda llamada
    # devuelve la orden tal como quedó, sin volver a procesar nada.
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)


class CompletarOrdenIn(BaseModel):
    resultado: str
    cantidad_producida: Decimal | None = Field(default=None, gt=0)
    horas_hombre: Decimal | None = Field(default=None, ge=0)
    merma_cantidad: Decimal | None = Field(default=None, gt=0)
    merma_motivo: str | None = None
    evidencia_destruccion_url: str | None = None
    # Trazabilidad del lote (RN-LOT-002/003, RN-VNC-001): solo tiene efecto
    # cuando `resultado="conforme"` — es lo que produce el lote del producto
    # terminado. Sin `fecha_vencimiento` el lote nace sin vencimiento y FEFO
    # lo trata como FIFO (deuda técnica ya cerrada por este bloque).
    fecha_vencimiento: date | None = None
    lote_codigo: str | None = Field(default=None, max_length=50)
    trazabilidad: dict | None = None
    # Mismo criterio que en `ConsumoCreate`.
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)
