"""DTOs (pydantic) del módulo assets."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Literales y no derivados de `domain.rules`: un `Literal[*tupla]` no sirve al
# type checker ni al esquema OpenAPI, que es el punto de tenerlos (mismo
# criterio que `purchases.api.schemas`). Que no se separen del dominio lo fija
# un caso en `tests/test_assets.py`.
TipoActivo = Literal["equipamiento", "vehiculo"]
EstadoActivo = Literal["operativo", "en_mantenimiento", "de_baja"]
TipoVehiculo = Literal["moto", "auto", "camioneta", "camion", "otro"]
TenenciaVehiculo = Literal["propio", "alquilado"]
OrigenLectura = Literal["manual", "carga_combustible", "mantenimiento"]
TipoOrdenMantenimiento = Literal["programado", "adelantado"]
MotivoAdelanto = Literal["desperfecto", "baja_productividad"]
EstadoOrdenMantenimiento = Literal["programada", "en_curso", "realizada", "cancelada"]
TipoDocumento = Literal[
    "soat",
    "revision_tecnica",
    "tarjeta_propiedad",
    "poliza_seguro",
    "garantia",
    "licencia_funcionamiento",
    "certificado_defensa_civil",
    "fumigacion",
    "registro_sanitario",
    "carne_sanidad",
    "licencia_conducir",
    "otro",
]
SujetoDocumento = Literal["activo", "sucursal", "empresa", "trabajador"]


class ActivoCreate(BaseModel):
    tipo: TipoActivo
    id_interno: str = Field(min_length=1, max_length=8)
    nombre: str = Field(min_length=1, max_length=150)
    sucursal_id: uuid.UUID | None = None
    categoria: str | None = Field(default=None, max_length=60)
    marca: str | None = Field(default=None, max_length=60)
    modelo: str | None = Field(default=None, max_length=60)
    numero_serie: str | None = Field(default=None, max_length=80)
    etiqueta_codigo: str | None = Field(default=None, max_length=40)
    fecha_compra: date | None = None
    valor_compra: Decimal | None = Field(default=None, ge=0)
    vida_util_meses: int | None = Field(default=None, gt=0)
    proveedor_id: uuid.UUID | None = None
    comprobante_compra_id: uuid.UUID | None = None
    responsable_trabajador_id: uuid.UUID | None = None
    notas: str | None = None
    # Solo si tipo == "vehiculo":
    placa: str | None = Field(default=None, max_length=10)
    tipo_vehiculo: TipoVehiculo | None = None
    numero_motor: str | None = Field(default=None, max_length=40)
    numero_chasis: str | None = Field(default=None, max_length=40)
    tenencia: TenenciaVehiculo = "propio"
    kilometraje_inicial: int | None = Field(default=None, ge=0)


class ActivoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=150)
    sucursal_id: uuid.UUID | None = None
    categoria: str | None = Field(default=None, max_length=60)
    marca: str | None = Field(default=None, max_length=60)
    modelo: str | None = Field(default=None, max_length=60)
    numero_serie: str | None = Field(default=None, max_length=80)
    etiqueta_codigo: str | None = Field(default=None, max_length=40)
    valor_compra: Decimal | None = Field(default=None, ge=0)
    vida_util_meses: int | None = Field(default=None, gt=0)
    responsable_trabajador_id: uuid.UUID | None = None
    notas: str | None = None


class ActivoBaja(BaseModel):
    motivo: str = Field(min_length=1, max_length=255)


class VehiculoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    placa: str
    tipo_vehiculo: str
    numero_motor: str | None
    numero_chasis: str | None
    tenencia: str
    kilometraje_actual: int | None


class ActivoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    sucursal_id: uuid.UUID | None
    tipo: str
    id_interno: str
    nombre: str
    categoria: str | None
    marca: str | None
    modelo: str | None
    numero_serie: str | None
    etiqueta_codigo: str | None
    fecha_compra: date | None
    valor_compra: Decimal | None
    vida_util_meses: int | None
    responsable_trabajador_id: uuid.UUID | None
    estado: str
    archivado: bool
    notas: str | None
    vehiculo: VehiculoOut | None = None


class LecturaOdometroCreate(BaseModel):
    km: int = Field(ge=0)
    fecha: date
    nota: str | None = None


class LecturaOdometroOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    vehiculo_id: uuid.UUID
    fecha: date
    km: int
    origen: str
    registrado_por: uuid.UUID
    nota: str | None


class CargaCombustibleCreate(BaseModel):
    comprobante_id: uuid.UUID
    fecha: date
    galones: Decimal = Field(gt=0, max_digits=8, decimal_places=3)
    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    km_odometro: int = Field(ge=0)
    tipo_combustible: str | None = Field(default=None, max_length=20)


class CargaCombustibleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    vehiculo_id: uuid.UUID
    fecha: date
    galones: Decimal
    monto: Decimal
    tipo_combustible: str | None
    km_odometro: int
    comprobante_id: uuid.UUID
    km_recorridos: int | None
    rendimiento_km_gal: Decimal | None
    anomalo: bool
    registrado_por: uuid.UUID


class ResumenConsumoOut(BaseModel):
    cargas: int
    promedio_km_gal: Decimal | None
    anomalas: int


class ComprobanteDisponibleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    emisor_num_doc: str | None
    tipo: str
    serie: str
    correlativo: int
    fecha_emision: date | None
    total: Decimal | None


class PlanMantenimientoCreate(BaseModel):
    activo_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=150)
    descripcion: str | None = None
    cada_dias: int | None = Field(default=None, gt=0)
    cada_km: int | None = Field(default=None, gt=0)
    dias_aviso: int = Field(default=15, ge=0)
    km_aviso: int = Field(default=500, ge=0)
    proveedor_servicio_id: uuid.UUID | None = None


class PlanMantenimientoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=150)
    descripcion: str | None = None
    cada_dias: int | None = Field(default=None, gt=0)
    cada_km: int | None = Field(default=None, gt=0)
    dias_aviso: int | None = Field(default=None, ge=0)
    km_aviso: int | None = Field(default=None, ge=0)
    activo: bool | None = None


class PlanMantenimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    activo_id: uuid.UUID
    nombre: str
    descripcion: str | None
    cada_dias: int | None
    cada_km: int | None
    dias_aviso: int
    km_aviso: int
    ultima_fecha: date | None
    ultimo_km: int | None
    activo: bool
    # Derivado, no columna: se calcula al leer (`planes.estado_de`).
    estado: str | None = None
    proxima_fecha: date | None = None
    proximo_km: int | None = None


class OrdenMantenimientoCreate(BaseModel):
    activo_id: uuid.UUID
    tipo: TipoOrdenMantenimiento
    plan_id: uuid.UUID | None = None
    motivo_adelanto: MotivoAdelanto | None = None
    fecha_programada: date | None = None
    proveedor_servicio_id: uuid.UUID | None = None
    descripcion: str | None = None


class OrdenMantenimientoRealizar(BaseModel):
    fecha_realizada: date
    km_al_realizar: int | None = Field(default=None, ge=0)
    resultado: str | None = None
    costo: Decimal | None = Field(default=None, ge=0)
    comprobante_id: uuid.UUID | None = None


class OrdenMantenimientoCancelar(BaseModel):
    motivo: str = Field(min_length=1, max_length=255)


class OrdenMantenimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    activo_id: uuid.UUID
    plan_id: uuid.UUID | None
    tipo: str
    motivo_adelanto: str | None
    fecha_programada: date | None
    fecha_realizada: date | None
    km_al_realizar: int | None
    proveedor_servicio_id: uuid.UUID | None
    reportado_por: uuid.UUID
    descripcion: str | None
    resultado: str | None
    costo: Decimal | None
    comprobante_id: uuid.UUID | None
    estado: str


class DocumentoVigenciaCreate(BaseModel):
    sujeto_tipo: SujetoDocumento
    sujeto_id: uuid.UUID
    tipo_documento: TipoDocumento
    fecha_vencimiento: date
    numero: str | None = Field(default=None, max_length=60)
    emisor: str | None = Field(default=None, max_length=120)
    fecha_emision: date | None = None
    dias_aviso: int = Field(default=30, ge=0)
    notas: str | None = None


class DocumentoVigenciaUpdate(BaseModel):
    numero: str | None = Field(default=None, max_length=60)
    emisor: str | None = Field(default=None, max_length=120)
    fecha_vencimiento: date | None = None
    dias_aviso: int | None = Field(default=None, ge=0)
    notas: str | None = None


class DocumentoVigenciaRenovar(BaseModel):
    fecha_vencimiento: date
    numero: str | None = Field(default=None, max_length=60)
    emisor: str | None = Field(default=None, max_length=120)
    fecha_emision: date | None = None


class DocumentoVigenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    sujeto_tipo: str
    sujeto_id: uuid.UUID
    tipo_documento: str
    numero: str | None
    emisor: str | None
    fecha_emision: date | None
    fecha_vencimiento: date
    dias_aviso: int
    renovado_por_id: uuid.UUID | None
    notas: str | None
    # Derivado: vigente | proximo | vencido | renovado.
    estado: str | None = None


class ArchivoAdjuntoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    tamano_bytes: int = Field(gt=0)
    url_storage: str = Field(min_length=1, max_length=500)


class ArchivoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    mime_type: str
    tamano_bytes: int
    url_storage: str
    created_at: datetime


class CronogramaItemOut(BaseModel):
    tipo: Literal["mantenimiento", "documento"]
    estado: str
    fecha: date | None
    km: int | None
    nombre: str
    activo_id: uuid.UUID | None = None
    plan_id: uuid.UUID | None = None
    documento_id: uuid.UUID | None = None
    sujeto_tipo: str | None = None
    sujeto_id: uuid.UUID | None = None
