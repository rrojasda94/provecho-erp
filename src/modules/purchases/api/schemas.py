"""DTOs (pydantic) del módulo purchases."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProveedorCreate(BaseModel):
    # `empresa_id` sale del JWT (ADR-004). Solo un superusuario sin empresa
    # asignada puede indicarla; a cualquier otro usuario, una empresa
    # distinta a la suya le responde 403.
    empresa_id: uuid.UUID | None = None
    tipo: str
    condicion_pago: str
    persona_id: uuid.UUID | None = None
    razon_social: str | None = Field(default=None, max_length=255)
    ruc: str | None = Field(default=None, min_length=11, max_length=11)
    contacto: str | None = Field(default=None, max_length=255)
    # Domicilio fiscal. Llega prellenado desde `GET /consulta/ruc/{n}`
    # y sigue siendo editable: SUNAT tiene el domicilio declarado, que
    # no siempre es el almacén al que uno va a recoger.
    direccion: str | None = Field(default=None, max_length=255)
    provincia: str | None = Field(default=None, max_length=100)
    pais: str = Field(default="PE", max_length=60)
    formal: bool = True
    clasificacion: str = "regular"
    plazo_dias_credito: int | None = None
    afecto_igv: bool = True
    sujeto_spot: bool = False
    porcentaje_deteccion: Decimal | None = None


class ProveedorUpdate(BaseModel):
    """Campo ausente o `null` = no tocar.

    `razon_social`/`ruc` se admiten porque un RUC mal tecleado llega hasta la
    factura electrónica: sin esto la única corrección era tocar la base. Solo
    valen sobre un proveedor **jurídico** — en uno natural esos datos viven
    en su `persona` (RN-GEN-007) y se corrigen allá.

    `tipo` y `persona_id` no son editables: cambiarlos convierte al proveedor
    en otro y deja sus órdenes de compra apuntando a algo que ya no es.
    """

    razon_social: str | None = Field(default=None, min_length=1, max_length=255)
    ruc: str | None = Field(default=None, pattern=r"^\d{11}$")
    contacto: str | None = Field(default=None, max_length=255)
    direccion: str | None = Field(default=None, max_length=255)
    provincia: str | None = Field(default=None, max_length=100)
    pais: str | None = Field(default=None, max_length=60)
    # `Literal` y no `str`: las tres columnas son `Enum` con CHECK, así que un
    # valor fuera de rango moría en el flush con un 500. Acá es un 422.
    clasificacion: Literal["regular", "preferente"] | None = None
    activo: bool | None = None
    condicion_pago: Literal["contado", "credito"] | None = None
    plazo_dias_credito: int | None = Field(default=None, ge=1)


class ProveedorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    tipo: str
    # Si tipo=natural: nombre/documento se resuelven en `persona` a partir
    # de esto (RN-GEN-007) — antes ni siquiera viajaba, así que un
    # proveedor natural no tenía forma de mostrarse por nombre.
    persona_id: uuid.UUID | None
    razon_social: str | None
    ruc: str | None
    # Los dos viajan para que el formulario de edición pueda precargarlos:
    # un campo que no se lee no se puede corregir sin borrarlo primero.
    contacto: str | None
    direccion: str | None
    provincia: str | None
    pais: str
    plazo_dias_credito: int | None
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
    # Lote del proveedor: solo lo usa inventory si el artículo controla lote
    # (RN-VNC-002). Sin código, el ERP lo deriva del vencimiento.
    lote_codigo: str | None = Field(default=None, max_length=50)
    fecha_vencimiento: date | None = None


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
