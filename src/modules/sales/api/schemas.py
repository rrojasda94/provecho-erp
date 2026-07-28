"""DTOs (pydantic) del módulo sales."""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# El precio NO viaja en el request: lo fija el servidor contra
# `lista_precio` (RN-PRC-003). `venta_item.precio_unitario` guarda el
# snapshot de lo resuelto.
class VentaItemIn(BaseModel):
    producto_comercial_id: uuid.UUID
    cantidad: Decimal = Field(gt=0)


class VentaCreate(BaseModel):
    sucursal_id: uuid.UUID
    punto_venta_id: uuid.UUID
    canal: str
    modalidad: str
    idempotency_key: str = Field(min_length=8, max_length=100)
    items: list[VentaItemIn] = Field(min_length=1)
    cliente_id: uuid.UUID | None = None
    # "Mesa 5", "Carlos", "Rappi #1042" — visible en KDS y comanda.
    referencia_atencion: str | None = Field(default=None, max_length=50)
    # Identificador generado por el cliente. El PDV puede crear la venta sin
    # conexión y conservar su id al llegar al servidor (ADR-009); si no lo
    # manda, lo genera el servidor como siempre.
    id: uuid.UUID | None = None


class VentaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sucursal_id: uuid.UUID
    fecha_orden: date
    numero_orden: int
    canal: str
    modalidad: str
    estado: str
    total: Decimal
    referencia_atencion: str | None


class PagoCreate(BaseModel):
    medio_pago_id: uuid.UUID
    monto: Decimal = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=100)
    referencia_externa: str | None = None
    id: uuid.UUID | None = None


class PagoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    venta_id: uuid.UUID
    medio_pago_id: uuid.UUID
    monto: Decimal
    estado: str


# --- Lote de sincronización del hub (ADR-009) -------------------------------
# Lo consume `core/sync` en `POST /sync/push`. Vive acá y no en `core`
# porque el contenido es dominio de sales: quien define qué es una venta
# válida es el módulo que la implementa.
class VentaItemSyncIn(BaseModel):
    """Ítem de una venta que YA se cobró en el hub. A diferencia del PDV en
    línea, acá el precio sí viaja: es el que el cliente pagó. Resolverlo de
    nuevo en la nube cambiaría el monto si la promoción venció entre el
    corte y la sincronización (RN-PRC-003 no admite recotizar lo cobrado).
    """

    producto_comercial_id: uuid.UUID
    cantidad: Decimal = Field(gt=0)
    precio_unitario: Decimal = Field(ge=0)
    descuento: Decimal = Decimal(0)


class VentaSyncIn(BaseModel):
    """Una venta ya ocurrida en el hub, tal cual, para reproducirla en la
    nube. Trae lo que la nube no puede reconstruir: identificador, día y
    número de orden que el cliente ya vio impresos, y quién la atendió."""

    id: uuid.UUID
    sucursal_id: uuid.UUID
    punto_venta_id: uuid.UUID
    canal: str
    modalidad: str
    usuario_id: uuid.UUID
    idempotency_key: str = Field(min_length=8, max_length=100)
    fecha_orden: date
    numero_orden: int = Field(ge=1)
    estado: str
    items: list[VentaItemSyncIn] = Field(min_length=1)
    cliente_id: uuid.UUID | None = None
    referencia_atencion: str | None = Field(default=None, max_length=50)


class PagoSyncIn(BaseModel):
    id: uuid.UUID
    venta_id: uuid.UUID
    medio_pago_id: uuid.UUID
    monto: Decimal = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=100)
    referencia_externa: str | None = None


class LoteSyncIn(BaseModel):
    ventas: list[VentaSyncIn] = []
    pagos: list[PagoSyncIn] = []


class ProductoCreate(BaseModel):
    id_interno: str = Field(min_length=1, max_length=4)
    marca_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=150)
    receta_id: uuid.UUID
    empaque_id: uuid.UUID | None = None
    modalidades_empaque: list[str] | None = None


class ProductoUpdate(BaseModel):
    nombre: str | None = None
    activo: bool | None = None
    empaque_id: uuid.UUID | None = None
    modalidades_empaque: list[str] | None = None


class ProductoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    id_interno: str
    marca_id: uuid.UUID
    nombre: str
    receta_id: uuid.UUID
    activo: bool


class MedioPagoCreate(BaseModel):
    # Derivado del JWT (ADR-004); solo un superusuario sin empresa asignada
    # puede indicarlo.
    empresa_id: uuid.UUID | None = None
    nombre: str = Field(min_length=1, max_length=50)
    direccion: str = "cobro"
    tipo: str
    comision_pct: Decimal = Decimal(0)


# --- Precios (server-side, RN-PRC-003) ---
class ListaPrecioCreate(BaseModel):
    marca_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=100)
    vigente_desde: date
    vigente_hasta: date | None = None
    sucursal_id: uuid.UUID | None = None
    canal: str | None = None
    modalidad: str | None = None
    es_promocional: bool = False


class ListaPrecioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    marca_id: uuid.UUID
    nombre: str
    sucursal_id: uuid.UUID | None
    canal: str | None
    modalidad: str | None
    es_promocional: bool
    vigente_desde: date
    vigente_hasta: date | None
    activa: bool


class PrecioCreate(BaseModel):
    producto_comercial_id: uuid.UUID
    monto: Decimal = Field(ge=0)


class PrecioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    lista_precio_id: uuid.UUID
    producto_comercial_id: uuid.UUID
    monto: Decimal


class CartaItemOut(BaseModel):
    producto_comercial_id: uuid.UUID
    id_interno: str
    nombre: str
    categoria_id: uuid.UUID | None
    precio_unitario: Decimal


class ClientePublicoOut(BaseModel):
    id: uuid.UUID
    tipo: str
    nombre: str | None
    contacto: str | None


class MedioPagoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    nombre: str
    tipo: str
    comision_pct: Decimal
    activo: bool


class ComprobanteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    venta_id: uuid.UUID | None
    tipo: str
    serie: str
    correlativo: int
    estado_emision: str
    hash_proveedor: str | None
    detalle_emision: str | None
    intentos_emision: int


class EntregaOut(BaseModel):
    venta_id: str
    numero_orden: int
    modalidad: str
    estado_pedido: str
    ya_entregado: bool
