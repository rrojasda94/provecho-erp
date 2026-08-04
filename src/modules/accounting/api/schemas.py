"""DTOs (pydantic) del módulo accounting."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CuentaContableCreate(BaseModel):
    # `empresa_id` sale del JWT (ADR-004). Solo un superusuario sin empresa
    # asignada puede indicarla.
    empresa_id: uuid.UUID | None = None
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=1, max_length=150)
    tipo: str
    cuenta_padre_id: uuid.UUID | None = None


class CuentaContableUpdate(BaseModel):
    nombre: str | None = None
    activa: bool | None = None


class CuentaContableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    codigo: str
    nombre: str
    tipo: str
    cuenta_padre_id: uuid.UUID | None
    activa: bool


class PeriodoContableCreate(BaseModel):
    # `empresa_id` sale del JWT (ADR-004). Solo un superusuario sin empresa
    # asignada puede indicarla.
    empresa_id: uuid.UUID | None = None
    anio: int = Field(ge=2000, le=2100)
    mes: int = Field(ge=1, le=12)


class PeriodoContableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    anio: int
    mes: int
    estado: str
    fecha_cierre: datetime | None


class AsientoLineaIn(BaseModel):
    cuenta_contable_id: uuid.UUID
    tipo: str
    monto: Decimal = Field(gt=0)


class AsientoLineaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    cuenta_contable_id: uuid.UUID
    tipo: str
    monto: Decimal


class AsientoManualCreate(BaseModel):
    # `empresa_id` sale del JWT (ADR-004). Solo un superusuario sin empresa
    # asignada puede indicarla.
    empresa_id: uuid.UUID | None = None
    fecha: date
    glosa: str = Field(min_length=1, max_length=255)
    lineas: list[AsientoLineaIn] = Field(min_length=2)


class AsientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    periodo_contable_id: uuid.UUID
    fecha: date
    glosa: str
    origen: str
    evento_origen: str | None
    referencia_origen: str | None
    estado: str
    asiento_reversa_de_id: uuid.UUID | None


class ReglaAsientoCreate(BaseModel):
    # `empresa_id` sale del JWT (ADR-004). Solo un superusuario sin empresa
    # asignada puede indicarla.
    empresa_id: uuid.UUID | None = None
    evento: str = Field(min_length=1, max_length=100)
    cuenta_debe_id: uuid.UUID
    cuenta_haber_id: uuid.UUID


class ReglaAsientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    evento: str
    cuenta_debe_id: uuid.UUID
    cuenta_haber_id: uuid.UUID
    activa: bool


class PagoProveedorCreate(BaseModel):
    # `empresa_id` sale del JWT (ADR-004). Solo un superusuario sin empresa
    # asignada puede indicarla.
    empresa_id: uuid.UUID | None = None
    comprobante_id: uuid.UUID | None = None
    proveedor_id: uuid.UUID | None = None
    orden_compra_id: uuid.UUID | None = None
    monto: Decimal = Field(gt=0)
    monto_detraccion: Decimal | None = Field(default=None, ge=0)


class EjecutarPagoIn(BaseModel):
    medio_pago: str
    constancia: str | None = Field(default=None, max_length=255)


# --- Caja (PROC-CTB-001/002) -------------------------------------------------
class PosVerificadoIn(BaseModel):
    """Estado de un POS de tarjeta al abrir la caja (RN-POS-010/011)."""

    pos_tarjeta_id: uuid.UUID
    operativo: bool = True
    observacion: str | None = Field(default=None, max_length=200)


class AbrirCajaIn(BaseModel):
    """`monto_declarado` es lo que el encargado dice entregar;
    `detalle_denominaciones` es lo que el cajero cuenta. La diferencia la
    calcula el servidor (RN-POS-011/012) — nunca se teclea.

    `autorizacion` es el token de `POST /auth/autorizar` del encargado que
    releva: sin su PIN no hay cadena de custodia (RN-MDP-002).
    """

    punto_venta_id: uuid.UUID
    monto_declarado: Decimal = Field(ge=0)
    detalle_denominaciones: dict[str, int]
    autorizacion: str
    pos_verificados: list[PosVerificadoIn] | None = None


class AperturaCajaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    punto_venta_id: uuid.UUID
    cajero_id: uuid.UUID
    relevo_encargado_id: uuid.UUID
    monto_apertura: Decimal
    detalle_denominaciones: dict | None
    diferencia_reportada: Decimal | None
    pos_verificados: list | None
    created_at: datetime


class CerrarCajaIn(BaseModel):
    """El monto real sale del conteo por denominación (RN-POS-007), y el
    efectivo se entrega al encargado que firma con su PIN (RN-MDP-002)."""

    detalle_denominaciones: dict[str, int]
    custodia: str
    autorizacion: str
    descuadre_atribucion: str | None = None


class CierreCajaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    apertura_caja_id: uuid.UUID
    cajero_id: uuid.UUID
    montos_esperados: dict | None
    descuadre_monto: Decimal
    descuadre_atribucion: str | None
    custodia: str
    estado: str
    correcciones: list | None
    created_at: datetime


class ReabrirCierreIn(BaseModel):
    motivo: str = Field(min_length=5, max_length=200)
    autorizacion: str


class CustodiaEfectivoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    apertura_caja_id: uuid.UUID
    monto: Decimal
    responsable_actual_id: uuid.UUID
    estado: str
    timestamps_relevo: list | None


class EntregarCustodiaIn(BaseModel):
    estado_siguiente: str = Field(pattern="^(en_supervisor|en_contabilidad|disponible)$")
    autorizacion: str


class PosTarjetaIn(BaseModel):
    serie: str = Field(min_length=2, max_length=50)
    codigo_comercio: str = Field(min_length=2, max_length=50)
    empresa_id: uuid.UUID | None = None
    # NULL = terminal de emergencia del pool de contabilidad (RN-POS-009).
    sucursal_id: uuid.UUID | None = None
    operador: str | None = Field(default=None, max_length=50)
    es_emergencia: bool = False


class PosTarjetaPatch(BaseModel):
    estado: str | None = Field(default=None, pattern="^(operativo|averiado|baja)$")
    sucursal_id: uuid.UUID | None = None
    es_emergencia: bool | None = None


class PosTarjetaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    sucursal_id: uuid.UUID | None
    serie: str
    codigo_comercio: str
    operador: str | None
    estado: str
    es_emergencia: bool


class MovimientoCajaIn(BaseModel):
    """Ingreso o retiro de efectivo del cajón durante el turno (RN-MDP-007).

    `autorizacion` es el token de `POST /auth/autorizar` y solo hace falta
    para retirar: meter plata al cajón no es la operación de la que hay que
    desconfiar.
    """

    tipo: str = Field(pattern="^(ingreso|retiro)$")
    monto: Decimal = Field(gt=0)
    motivo: str = Field(min_length=3, max_length=120)
    idempotency_key: str = Field(min_length=8, max_length=100)
    autorizacion: str | None = None


class MovimientoCajaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    apertura_caja_id: uuid.UUID
    tipo: str
    monto: Decimal
    motivo: str
    registrado_por: uuid.UUID
    autorizado_por: uuid.UUID | None


class ArqueoIn(BaseModel):
    punto_venta_id: uuid.UUID
    tipo: str
    monto_contado: Decimal = Field(ge=0)


class ArqueoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    punto_venta_id: uuid.UUID
    tipo: str
    realizado_por: uuid.UUID
    monto_esperado: Decimal
    monto_contado: Decimal
    diferencia: Decimal
    created_at: datetime


class CajaAbiertaOut(BaseModel):
    apertura_caja_id: uuid.UUID
    punto_venta_id: uuid.UUID
    cajero_id: uuid.UUID
    monto_apertura: Decimal
    abierta_desde: datetime


class MovimientoDineroOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    tipo: str
    concepto: str
    comprobante_id: uuid.UUID | None
    proveedor_id: uuid.UUID | None
    orden_compra_id: uuid.UUID | None
    monto: Decimal
    monto_detraccion: Decimal | None
    medio_pago: str | None
    estado: str
    asiento_id: uuid.UUID | None
    fecha_ejecucion: datetime | None
    constancia: str | None
