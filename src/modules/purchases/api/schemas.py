"""DTOs (pydantic) del módulo purchases."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.shared.ubicacion import UbicacionMixin

# Se escriben literales y no se derivan de `rules`: `Literal[*tupla]` no le
# sirve al type checker ni al esquema de OpenAPI, que es el punto de tenerlos.
# Que no se separen del dominio lo fija un caso en `tests/test_purchases.py`.
TipoRecibido = Literal["factura", "boleta", "rhe", "ticket_compra"]
Sustento = Literal[
    "efectivo", "voucher_medio_pago", "movimiento_bancario", "contrato_credito"
]


class ProveedorCreate(UbicacionMixin):
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


class ProveedorUpdate(UbicacionMixin):
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


class ProveedorOut(UbicacionMixin):
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


class OrdenCompraItemsUpdate(BaseModel):
    """Reemplaza los ítems de una OC — solo admitido en `estado='borrador'`."""

    items: list[OrdenCompraItemIn] = Field(min_length=1)


class OrdenCompraItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    articulo_id: uuid.UUID
    cantidad: Decimal
    costo_unitario: Decimal
    cantidad_recibida: Decimal


class OrdenCompraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    proveedor_id: uuid.UUID
    tipo: str
    origen: str
    almacen_destino_id: uuid.UUID
    estado: str
    total: Decimal
    items: list[OrdenCompraItemOut] = []


class ComprobanteProveedorBase(BaseModel):
    """Los datos del papel que entregó el proveedor.

    `Literal` y no `str`: `comprobante.tipo` y `comprobante.sustento` son
    columnas `Enum` con CHECK, así que hasta 2026-08-30 un valor fuera de
    rango no se rechazaba acá — moría en el `flush` con un **500** que no
    decía qué campo estaba mal. Es el mismo defecto que `ProveedorUpdate` ya
    había corregido con `Literal`.
    """

    idempotency_key: str = Field(min_length=8, max_length=100)
    tipo: TipoRecibido
    serie: str = Field(min_length=1, max_length=10)
    correlativo: int = Field(gt=0)
    sustento: Sustento
    # RUC (11) o DNI (8 — un RHE de persona natural). Ausente = se toma el
    # del proveedor de la OC: el emisor es él, y tecleado dos veces son dos
    # verdades. Se manda solo cuando el papel lo desmiente (una factura de
    # otra razón social del mismo grupo, por ejemplo).
    emisor_num_doc: str | None = Field(default=None, pattern=r"^(\d{8}|\d{11})$")
    # La fecha del papel, que es la que manda en el Registro de Compras. Sin
    # ella lo único que quedaba era cuándo se tecleó.
    fecha_emision: date | None = None
    # El importe del papel, IGV incluido. Puede diferir del total de la OC
    # —que es la base de lo recibido— y por eso es un dato propio y no algo
    # que se derive.
    total: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    # ¿La factura del proveedor trae IGV? Lo marca quien la tiene delante:
    # una empresa de Amazonía vende exonerada y aun así compra con IGV a un
    # proveedor de fuera de la región, y ese crédito fiscal se registra
    # recién acá. `None` = manda el default de la empresa.
    gravado_igv: bool | None = None


class CompraDirectaComprobante(ComprobanteProveedorBase):
    pass


class CompraDirectaCreate(BaseModel):
    proveedor_id: uuid.UUID
    almacen_destino_id: uuid.UUID
    idempotency_key: str = Field(min_length=8, max_length=100)
    items: list[OrdenCompraItemIn] = Field(min_length=1)
    comprobante: CompraDirectaComprobante


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


class ConformidadComprobanteCreate(ComprobanteProveedorBase):
    pass


class RecepcionItemOut(BaseModel):
    id: uuid.UUID
    orden_compra_item_id: uuid.UUID
    # Resuelto desde el ítem de la OC: `recepcion_item` no lo guarda, y sin
    # él la ficha mostraría el UUID de una línea.
    articulo_id: uuid.UUID
    cantidad_recibida: Decimal
    costo_unitario: Decimal
    lote_codigo: str | None
    fecha_vencimiento: date | None


class RecepcionDetalleOut(BaseModel):
    id: uuid.UUID
    orden_compra_id: uuid.UUID
    recibido_por: uuid.UUID
    fecha: datetime
    comprobante_id: uuid.UUID | None
    items: list[RecepcionItemOut] = []


class ComprobanteRecibidoOut(BaseModel):
    """Una fila del registro de compras.

    `total` es lo que declara el papel y `total_orden` lo que la OC dice que
    se recibió (base, sin IGV). Viajan los dos y no uno "el" total: son
    números distintos por definición, y elegir cuál mostrar escondería la
    diferencia, que es justo lo que hay que conciliar.
    """

    id: uuid.UUID
    empresa_id: uuid.UUID
    compra_id: uuid.UUID | None
    proveedor_id: uuid.UUID | None = None
    proveedor: str | None = None
    emisor_num_doc: str | None
    tipo: str
    serie: str
    correlativo: int
    fecha_emision: date | None
    total: Decimal | None
    total_orden: Decimal | None = None
    sustento: str
    gravado_igv: bool | None
    created_at: datetime


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
    emisor_num_doc: str | None = None
    fecha_emision: date | None = None
    total: Decimal | None = None
