"""DTOs (pydantic) del módulo inventory."""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# --- Categorías ---
# `empresa_id` sale del JWT (ADR-004). Solo un superusuario sin empresa
# asignada puede indicarla; a cualquier otro usuario, una empresa distinta
# a la suya le responde 403.
class CategoriaCreate(BaseModel):
    empresa_id: uuid.UUID | None = None
    nombre: str = Field(min_length=1, max_length=100)
    asiento_contable_config: dict | None = None


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    nombre: str


# --- Artículos ---
class ArticuloCreate(BaseModel):
    empresa_id: uuid.UUID | None = None
    id_interno: str = Field(min_length=1, max_length=4)
    nombre: str = Field(min_length=1, max_length=150)
    unidad_medida_id: uuid.UUID
    tipo: str = Field(max_length=30)
    categoria_id: uuid.UUID | None = None
    costo_promedio: Decimal = Decimal(0)
    # Perecible o trazable → su stock se mueve por lote y respeta FEFO.
    controla_lote: bool = False


class ArticuloUpdate(BaseModel):
    nombre: str | None = None
    categoria_id: uuid.UUID | None = None
    tipo: str | None = None
    costo_promedio: Decimal | None = None
    archivado: bool | None = None
    controla_lote: bool | None = None


class ArticuloOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    id_interno: str
    nombre: str
    unidad_medida_id: uuid.UUID
    tipo: str
    categoria_id: uuid.UUID | None
    costo_promedio: Decimal
    archivado: bool
    controla_lote: bool


# --- SKU ---
class SkuCreate(BaseModel):
    articulo_id: uuid.UUID
    codigo: str = Field(min_length=1, max_length=50)
    codigo_barras: str | None = None


class SkuOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    articulo_id: uuid.UUID
    codigo: str
    codigo_barras: str | None
    activo: bool


# --- Stock / movimientos ---
class MovimientoCreate(BaseModel):
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal  # con signo: + ingreso, − salida
    tipo: str
    referencia: str | None = None
    # Override del lote sugerido por FEFO; NULL deja que el ERP lo elija.
    lote_id: uuid.UUID | None = None
    # Identificador generado por el cliente: permite que un dispositivo que
    # ya creó el movimiento sin conexión conserve su id (ADR-009).
    id: uuid.UUID | None = None


class MovimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal
    tipo: str
    lote_id: uuid.UUID | None


class StockOut(BaseModel):
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal
    stock_minimo: Decimal | None
    bajo_minimo: bool


# --- Lotes ---
class LoteCreate(BaseModel):
    articulo_id: uuid.UUID
    # Sin código, el ERP lo deriva del vencimiento (RN-LOT-001).
    codigo: str | None = Field(default=None, max_length=50)
    fecha_vencimiento: date | None = None
    fecha_elaboracion: date | None = None
    origen: str = "carga_inicial"
    referencia: str | None = None
    condicion_almacenamiento: str | None = None


class LoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    articulo_id: uuid.UUID
    codigo: str
    fecha_vencimiento: date | None
    fecha_elaboracion: date | None
    origen: str
    referencia: str | None
    condicion_almacenamiento: str | None


class StockLoteOut(BaseModel):
    """Saldo por lote — el listado que el picking lee en orden FEFO."""
    lote_id: uuid.UUID
    codigo: str
    articulo_id: uuid.UUID
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal
    estado: str
    fecha_vencimiento: date | None
    vencido: bool


# --- Ajustes ---
class AjusteCreate(BaseModel):
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal  # delta con signo
    motivo: str
    dentro_margen: bool = True


class AjusteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal
    motivo: str
    estado: str
    solicitado_por: uuid.UUID
    aprobado_por: uuid.UUID | None
    dentro_margen: bool
