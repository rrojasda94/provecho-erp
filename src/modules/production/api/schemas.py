"""DTOs (pydantic) del módulo production."""

import uuid
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


class ConsumoItemIn(BaseModel):
    articulo_id: uuid.UUID
    cantidad: Decimal = Field(gt=0)
    costo_unitario: Decimal = Field(ge=0)
    peso_desperdicio_real: Decimal = Decimal(0)
    tipo_desperdicio: str | None = None


class ConsumoCreate(BaseModel):
    items: list[ConsumoItemIn] = Field(min_length=1)


class CompletarOrdenIn(BaseModel):
    resultado: str
    cantidad_producida: Decimal | None = Field(default=None, gt=0)
    horas_hombre: Decimal | None = Field(default=None, ge=0)
    merma_cantidad: Decimal | None = Field(default=None, gt=0)
    merma_motivo: str | None = None
    evidencia_destruccion_url: str | None = None
