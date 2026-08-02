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
    # Cada cuánto se cuenta esta categoría (RN-INV-007). NULL = fuera del
    # conteo cíclico.
    frecuencia_conteo: str | None = None


class CategoriaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    asiento_contable_config: dict | None = None
    frecuencia_conteo: str | None = None
    # Único modo de volver a NULL: sin esto, `frecuencia_conteo=None` es
    # indistinguible de "no la mandaron".
    quitar_frecuencia: bool = False


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    nombre: str
    frecuencia_conteo: str | None


# --- Unidades de medida ---
# Catálogo global, no por empresa (a diferencia de categoría/artículo): la
# conversión kilo↔gramo es la misma para cualquier empresa que use el ERP.
class UnidadMedidaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    categoria_udm_id: uuid.UUID
    nombre: str
    ratio: Decimal
    decimales: int


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
    # `cantidad` es el stock físico; `disponible` = físico − reservas
    # activas (RN-INV-009), y es contra ese que se compromete stock nuevo.
    cantidad: Decimal
    reservado: Decimal
    disponible: Decimal
    stock_minimo: Decimal | None
    bajo_minimo: bool


# --- Reservas ---
class ReservaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal
    tipo: str
    referencia_id: uuid.UUID | None
    motivo: str | None
    estado: str


# --- Solicitud de insumos ---
class SolicitudItemIn(BaseModel):
    sku_id: uuid.UUID
    cantidad: Decimal = Field(gt=0)


class SolicitudCreate(BaseModel):
    almacen_solicitante_id: uuid.UUID
    # Sin esto se usa el `almacen_abastecedor_id` configurado en el almacén.
    almacen_abastecedor_id: uuid.UUID | None = None
    items: list[SolicitudItemIn] = Field(min_length=1)
    observacion: str | None = Field(default=None, max_length=500)


class SolicitudItemCantidad(BaseModel):
    sku_id: uuid.UUID
    cantidad: Decimal = Field(ge=0)


class SolicitudAprobar(BaseModel):
    """Recorte por SKU; lo que no se menciona se aprueba tal cual se pidió.
    Aprobar 0 deja el ítem fuera y no reserva nada."""
    aprobadas: list[SolicitudItemCantidad] = []


class SolicitudItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sku_id: uuid.UUID
    cantidad_solicitada: Decimal
    cantidad_aprobada: Decimal | None
    cantidad_despachada: Decimal | None


class SolicitudOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    almacen_solicitante_id: uuid.UUID
    almacen_abastecedor_id: uuid.UUID
    estado: str
    solicitado_por: uuid.UUID
    aprobado_por: uuid.UUID | None
    observacion: str | None


class SolicitudDetalleOut(SolicitudOut):
    items: list[SolicitudItemOut]


# --- Transferencias ---
class TransferenciaCreate(BaseModel):
    origen_almacen_id: uuid.UUID
    destino_almacen_id: uuid.UUID
    # Con solicitud, los ítems son opcionales: por defecto se despacha lo
    # aprobado. Sin solicitud (transferencia lateral) son obligatorios.
    solicitud_id: uuid.UUID | None = None
    items: list[SolicitudItemIn] = []
    transportista_id: uuid.UUID | None = None
    observacion: str | None = Field(default=None, max_length=500)


class TransferenciaRecibirItem(BaseModel):
    # Es el id del `transferencia_item`, no del SKU: una salida FEFO puede
    # repartir un mismo SKU entre varios lotes y cada lote se recibe aparte.
    item_id: uuid.UUID
    cantidad: Decimal = Field(ge=0)


class TransferenciaRecibir(BaseModel):
    """Lo que no se menciona se recibe completo."""
    items: list[TransferenciaRecibirItem] = []


class TransferenciaItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sku_id: uuid.UUID
    lote_id: uuid.UUID | None
    cantidad_enviada: Decimal
    cantidad_recibida: Decimal | None
    diferencia: Decimal | None


class TransferenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    origen_almacen_id: uuid.UUID
    destino_almacen_id: uuid.UUID
    solicitud_id: uuid.UUID | None
    estado: str
    despachado_por: uuid.UUID
    recibido_por: uuid.UUID | None
    transportista_id: uuid.UUID | None
    observacion: str | None


class TransferenciaDetalleOut(TransferenciaOut):
    items: list[TransferenciaItemOut]


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
    conteo_id: uuid.UUID | None
    solicitado_por: uuid.UUID
    aprobado_por: uuid.UUID | None
    dentro_margen: bool


# --- Conteo cíclico ---
class ConteoCreate(BaseModel):
    almacen_id: uuid.UUID
    # NULL = conteo general de todo el almacén.
    categoria_id: uuid.UUID | None = None
    tipo: str = "rutina"
    observacion: str | None = Field(default=None, max_length=500)


class ConteoCantidad(BaseModel):
    sku_id: uuid.UUID
    cantidad: Decimal = Field(ge=0)


class ConteoCantidades(BaseModel):
    items: list[ConteoCantidad] = Field(min_length=1)


class ConteoItemOut(BaseModel):
    sku_id: uuid.UUID
    cantidad_contada: Decimal | None
    # Ocultos al contador "a ciegas" (RN-INV-005): sin el permiso
    # `inventory.ver_stock_esperado` viajan en NULL.
    cantidad_sistema: Decimal | None = None
    diferencia: Decimal | None = None


class ConteoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    almacen_id: uuid.UUID
    categoria_id: uuid.UUID | None
    tipo: str
    estado: str
    fecha_programada: date | None
    abierto_por: uuid.UUID
    cerrado_por: uuid.UUID | None
    observacion: str | None


class ConteoDetalleOut(ConteoOut):
    items: list[ConteoItemOut]


class ConteoCierreOut(BaseModel):
    conteo: ConteoOut
    # Ajustes solicitados por las diferencias — nacen `pendiente` y los
    # aprueba alguien distinto de quien contó (RN-INV-006).
    ajustes: list[AjusteOut]


class ProgramaConteoOut(BaseModel):
    almacen_id: uuid.UUID
    categoria_id: uuid.UUID
    categoria: str
    frecuencia: str
    ultimo_conteo: date | None
    proxima_fecha: date
    estado: str  # al_dia | vence_hoy | vencido
    dias_atraso: int
