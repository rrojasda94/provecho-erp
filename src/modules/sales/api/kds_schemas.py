"""DTOs (pydantic) del KDS."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from src.modules.sales.api.schemas import EncabezadoImpresionOut


class PantallaCreate(BaseModel):
    sucursal_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=100)
    tipo: str  # preparacion | despacho
    categoria_ids: list[str] | None = None  # None/[] = todas las categorías
    # Eslabón en la cadena de preparación (ADR-044). 0 = la primera.
    orden: int = Field(default=0, ge=0)


class PantallaUpdate(BaseModel):
    nombre: str | None = None
    tipo: str | None = None
    categoria_ids: list[str] | None = None
    activo: bool | None = None
    orden: int | None = Field(default=None, ge=0)


class PantallaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sucursal_id: uuid.UUID
    nombre: str
    tipo: str
    categoria_ids: list[str] | None
    orden: int
    activo: bool


class ExtraColaOut(BaseModel):
    producto: str
    cantidad: str


class ItemColaOut(BaseModel):
    venta_item_id: str
    producto: str
    cantidad: str
    estado: str
    # Restas de la línea, ya resueltas a nombre: ["Cebolla"] → "SIN CEBOLLA"
    # en pantalla (RN-COM-028). Lista vacía = el plato va completo.
    sin: list[str] = []
    # Lo que el plato lleva además (el sabor de la pizza, el queso extra).
    # Anidados y no como ítems propios: en cocina son el mismo plato
    # (RN-CUP-014).
    extras: list[ExtraColaOut] = []
    etapa_kds: int = 0
    # Nombre de la estación donde está la línea ahora; `None` = ya salió de
    # cocina. Es lo que despacho muestra por línea (RN-CUP-013).
    estacion: str | None = None


class PedidoColaOut(BaseModel):
    venta_id: str
    numero_orden: int
    referencia_atencion: str | None
    modalidad: str
    canal: str
    # `venta` | `consumo_personal` (RN-COM-025) y su motivo: la cocina
    # prioriza distinto la comida del turno que un pedido de cliente.
    tipo: str = "venta"
    consumo_motivo: str | None = None
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
    # Membrete de la marca: en un local multimarca todas las cocinas
    # imprimen en el mismo rollo (ADR-067).
    encabezado: EncabezadoImpresionOut
    texto: str
