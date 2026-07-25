"""DTOs (pydantic) del módulo purchases."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProveedorCreate(BaseModel):
    empresa_id: uuid.UUID
    tipo: str
    condicion_pago: str
    persona_id: uuid.UUID | None = None
    razon_social: str | None = Field(default=None, max_length=255)
    ruc: str | None = Field(default=None, min_length=11, max_length=11)
    contacto: str | None = Field(default=None, max_length=255)
    formal: bool = True
    clasificacion: str = "regular"
    plazo_dias_credito: int | None = None
    afecto_igv: bool = True
    sujeto_spot: bool = False
    porcentaje_deteccion: Decimal | None = None


class ProveedorUpdate(BaseModel):
    contacto: str | None = None
    clasificacion: str | None = None
    activo: bool | None = None
    condicion_pago: str | None = None
    plazo_dias_credito: int | None = None


class ProveedorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    tipo: str
    razon_social: str | None
    ruc: str | None
    formal: bool
    clasificacion: str
    condicion_pago: str
    activo: bool


class OrdenCompraItemIn(BaseModel):
    articulo_id: uuid.UUID
    cantidad: Decimal = Field(gt=0)
    costo_unitario: Decimal = Field(ge=0)


class OrdenCompraCreate(BaseModel):
    proveedor_id: uuid.UUID
    almacen_destino_id: uuid.UUID
    idempotency_key: str = Field(min_length=8, max_length=100)
    items: list[OrdenCompraItemIn] = Field(min_length=1)
    tipo: str = "insumo"


class OrdenCompraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    proveedor_id: uuid.UUID
    tipo: str
    almacen_destino_id: uuid.UUID
    estado: str
    total: Decimal


class RecepcionItemIn(BaseModel):
    orden_compra_item_id: uuid.UUID
    cantidad_recibida: Decimal = Field(gt=0)
    costo_unitario: Decimal | None = Field(default=None, ge=0)


class RecepcionCreate(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=100)
    items: list[RecepcionItemIn] = Field(min_length=1)


class RecepcionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    orden_compra_id: uuid.UUID
    recibido_por: uuid.UUID


class ConformidadComprobanteCreate(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=100)
    tipo: str
    serie: str = Field(min_length=1, max_length=10)
    correlativo: int = Field(gt=0)
    sustento: str


class ComprobanteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    compra_id: uuid.UUID | None
    direccion: str
    tipo: str
    serie: str
    correlativo: int
    sustento: str
