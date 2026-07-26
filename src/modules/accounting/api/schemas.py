"""DTOs (pydantic) del módulo accounting."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CuentaContableCreate(BaseModel):
    empresa_id: uuid.UUID
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
    empresa_id: uuid.UUID
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
    empresa_id: uuid.UUID
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
    empresa_id: uuid.UUID
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
    empresa_id: uuid.UUID
    comprobante_id: uuid.UUID | None = None
    proveedor_id: uuid.UUID | None = None
    orden_compra_id: uuid.UUID | None = None
    monto: Decimal = Field(gt=0)
    monto_detraccion: Decimal | None = Field(default=None, ge=0)


class EjecutarPagoIn(BaseModel):
    medio_pago: str
    constancia: str | None = Field(default=None, max_length=255)


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
