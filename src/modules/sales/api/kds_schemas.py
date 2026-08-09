"""DTOs (pydantic) del KDS."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class PantallaCreate(BaseModel):
    sucursal_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=100)
    tipo: str  # preparacion | despacho
    categoria_ids: list[str] | None = None  # None/[] = todas las categorías


class PantallaUpdate(BaseModel):
    nombre: str | None = None
    tipo: str | None = None
    categoria_ids: list[str] | None = None
    activo: bool | None = None


class PantallaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sucursal_id: uuid.UUID
    nombre: str
    tipo: str
    categoria_ids: list[str] | None
    activo: bool


class ItemColaOut(BaseModel):
    venta_item_id: str
    producto: str
    cantidad: str
    estado: str
    # Restas de la línea, ya resueltas a nombre: ["Cebolla"] → "SIN CEBOLLA"
    # en pantalla (RN-COM-028). Lista vacía = el plato va completo.
    sin: list[str] = []


class PedidoColaOut(BaseModel):
    venta_id: str
    numero_orden: int
    referencia_atencion: str | None
    modalidad: str
    canal: str
    estado_pedido: str
    items: list[ItemColaOut]


class AvanzarIn(BaseModel):
    estado: str  # en_preparacion | listo | entregado


class AvanceOut(BaseModel):
    venta_id: str
    numero_orden: int
    referencia_atencion: str | None
    estado_pedido: str
    items: list[ItemColaOut]


class ComandaOut(BaseModel):
    venta_id: str
    numero_orden: int
    reimpresion: bool
    impresa_veces: int
    texto: str
