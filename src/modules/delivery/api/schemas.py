"""DTOs (pydantic) del módulo delivery."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VehiculoTipo = Literal["moto", "bicicleta", "auto", "a_pie"]
MotivoFallo = Literal["cliente_ausente", "direccion_errada", "rechazo", "no_contesta", "otro"]

# Se escriben literales y no se derivan de `rules`: `Literal[*tupla]` no le
# sirve al type checker ni al esquema OpenAPI, que es el punto de tenerlos.
# Que no se separen del dominio lo fija un caso en `tests/test_delivery.py`.


class RepartidorCandidatoOut(BaseModel):
    trabajador_id: uuid.UUID
    usuario_id: uuid.UUID
    nombre: str
    cargo: str
    sucursal_id: uuid.UUID | None


class RepartidorCreate(BaseModel):
    trabajador_id: uuid.UUID
    sucursal_id: uuid.UUID
    vehiculo_tipo: VehiculoTipo
    placa: str | None = Field(default=None, max_length=10)
    telefono: str | None = Field(default=None, max_length=20)


class RepartidorUpdate(BaseModel):
    """Campo ausente = no tocar."""

    sucursal_id: uuid.UUID | None = None
    vehiculo_tipo: VehiculoTipo | None = None
    placa: str | None = Field(default=None, max_length=10)
    telefono: str | None = Field(default=None, max_length=20)
    activo: bool | None = None


class RepartidorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    sucursal_id: uuid.UUID
    trabajador_id: uuid.UUID
    usuario_id: uuid.UUID
    #: `None` solo si la cuenta detrás del repartidor ya no existe.
    nombre: str | None = None
    vehiculo_tipo: str
    placa: str | None
    telefono: str | None
    activo: bool


class RutaCreate(BaseModel):
    sucursal_id: uuid.UUID
    repartidor_id: uuid.UUID
    venta_ids: list[uuid.UUID] = Field(min_length=1)
    #: `True` (por defecto) ordena por la heurística vecino-más-cercano;
    #: `False` respeta el orden en que llegaron los `venta_ids`.
    optimizar: bool = True


class RutaParadasUpdate(BaseModel):
    venta_ids: list[uuid.UUID] = Field(min_length=1)
    optimizar: bool = True


class RutaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sucursal_id: uuid.UUID
    repartidor_id: uuid.UUID
    creada_por: uuid.UUID
    estado: str
    hora_salida: datetime | None
    hora_fin: datetime | None
    origen_lat: Decimal
    origen_lng: Decimal
    distancia_m: int | None
    duracion_seg: int | None
    polyline: str | None
    optimizada_por: str
    ultima_lat: Decimal | None
    ultima_lng: Decimal | None
    ultima_precision_m: int | None
    ultima_posicion_at: datetime | None


class EntregaRepartoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    venta_id: uuid.UUID
    sucursal_id: uuid.UUID
    ruta_id: uuid.UUID | None
    repartidor_id: uuid.UUID | None
    #: Solo en `GET /delivery/entregas` (`entregas.historial_enriquecido`):
    #: la respuesta inmediata de entregar/fallar/reintentar/cerrar no lo
    #: resuelve, porque quien la recibe ya sabe a quién le acaba de pasar.
    repartidor_nombre: str | None = None
    orden_parada: int | None
    estado: str
    intentos: int
    eta_at: datetime | None
    tramo_distancia_m: int | None
    tramo_duracion_seg: int | None
    destino_lat: Decimal | None
    destino_lng: Decimal | None
    #: Igual que `repartidor_nombre`: solo en el historial.
    numero_orden: int | None = None
    direccion_entrega: str | None = None
    cliente_nombre: str | None = None
    fecha_entrega: datetime | None
    entregado_por: uuid.UUID | None
    motivo_fallo: str | None
    motivo_detalle: str | None
    resultado_lat: Decimal | None
    resultado_lng: Decimal | None
    observacion: str | None


# Tope tras decodificar el base64 — mismo criterio y mismo número que
# `rrhh.api.routers.FOTO_MAX_BYTES`: un JPEG de 320px al 60% pesa ~40 KB,
# esto deja margen sin abrir la puerta a subir cualquier cosa.
FOTO_MAX_BASE64 = 175_000


class EntregarIn(BaseModel):
    lat: Decimal | None = Field(default=None, ge=-90, le=90)
    lng: Decimal | None = Field(default=None, ge=-180, le=180)
    #: JPEG en base64, sin el encabezado `data:image/jpeg;base64,`.
    foto: str | None = Field(default=None, max_length=FOTO_MAX_BASE64)
    observacion: str | None = Field(default=None, max_length=255)


class FallarIn(BaseModel):
    motivo: MotivoFallo
    #: Obligatorio si `motivo="otro"` (RN-DLV-003) — se valida en la
    #: aplicación, no acá: el esquema no conoce el valor de otro campo.
    detalle: str | None = Field(default=None, max_length=255)
    lat: Decimal | None = Field(default=None, ge=-90, le=90)
    lng: Decimal | None = Field(default=None, ge=-180, le=180)
    foto: str | None = Field(default=None, max_length=FOTO_MAX_BASE64)


class VentaListaOut(BaseModel):
    id: uuid.UUID
    sucursal_id: uuid.UUID
    numero_orden: int
    fecha_orden: date
    cliente_id: uuid.UUID | None
    direccion_entrega: str | None
    ubicacion_lat: Decimal | None
    ubicacion_lng: Decimal | None
    distancia_entrega_km: Decimal | None


class ParadaRepartoOut(BaseModel):
    """Una parada de `GET /delivery/mi/rutas` o de `GET /delivery/tablero`,
    con la venta y el cliente ya resueltos: ni la PWA del repartidor ni el
    tablero de despacho llaman a `sales` ni a `rrhh` por su cuenta."""

    entrega_id: uuid.UUID
    venta_id: uuid.UUID
    orden_parada: int | None
    estado: str
    numero_orden: int | None
    direccion_entrega: str | None
    destino_lat: Decimal | None
    destino_lng: Decimal | None
    cliente_nombre: str | None
    cliente_telefono: str | None
    #: Solo si la venta sigue `orden` (sin pagar): lo que el repartidor
    #: cobra en la puerta. `None` si ya se pagó en caja.
    monto_a_cobrar: Decimal | None
    eta_at: datetime | None
    motivo_fallo: str | None
    #: Mismo enlace que recibe el cliente por WhatsApp — fallback copiable
    #: cuando el aviso automático no está configurado. `None` sin
    #: `DELIVERY_URL_PUBLICA` o sin token todavía.
    enlace_seguimiento: str | None


class RutaConParadasOut(BaseModel):
    """Una ruta con sus paradas ya resueltas — la misma vista compuesta
    sirve `GET /delivery/mi/rutas` (acotada a las del repartidor) y
    `GET /delivery/tablero` (las vivas de la sucursal, con
    `repartidor_nombre` para que el tablero no tenga que resolverlo)."""

    id: uuid.UUID
    sucursal_id: uuid.UUID
    repartidor_id: uuid.UUID
    repartidor_nombre: str | None
    estado: str
    hora_salida: datetime | None
    origen_lat: Decimal
    origen_lng: Decimal
    distancia_m: int | None
    duracion_seg: int | None
    polyline: str | None
    ultima_lat: Decimal | None
    ultima_lng: Decimal | None
    ultima_posicion_at: datetime | None
    paradas: list[ParadaRepartoOut]


class TableroOut(BaseModel):
    sin_asignar: list[VentaListaOut]
    rutas: list[RutaConParadasOut]
    #: Si el envío automático no está configurado, el tablero no ofrece
    #: "reenviar" — solo copiar/`wa.me`, que siempre funciona.
    whatsapp_habilitado: bool


class PosicionIn(BaseModel):
    lat: Decimal = Field(ge=-90, le=90)
    lng: Decimal = Field(ge=-180, le=180)
    precision_m: int | None = Field(default=None, ge=0)
    #: Reloj del teléfono, no el del servidor — ver
    #: `infrastructure/models/posicion_repartidor.py`.
    registrado_at: datetime


EstadoPublico = Literal["preparando", "en_camino", "entregado", "no_entregado"]


class SeguimientoSucursalOut(BaseModel):
    nombre: str


class SeguimientoRepartidorOut(BaseModel):
    #: Solo el primer nombre (RN-DLV-008).
    nombre: str


class SeguimientoPosicionOut(BaseModel):
    lat: Decimal
    lng: Decimal
    registrado_at: datetime | None


class SeguimientoDestinoOut(BaseModel):
    lat: Decimal | None
    lng: Decimal | None


class SeguimientoHitoOut(BaseModel):
    hito: str
    at: datetime | None


class SeguimientoOut(BaseModel):
    """Lo mínimo que ve el cliente por el enlace público (RN-DLV-008):
    nunca monto, teléfono, dirección en texto ni las demás paradas de la
    ruta."""

    estado_publico: EstadoPublico
    numero_orden: int | None
    sucursal: SeguimientoSucursalOut
    repartidor: SeguimientoRepartidorOut | None
    eta_at: datetime | None
    posicion: SeguimientoPosicionOut | None
    destino: SeguimientoDestinoOut
    linea_tiempo: list[SeguimientoHitoOut]
