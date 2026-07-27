"""DTOs (pydantic) del módulo rrhh."""

import uuid
from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

# --- Trabajador ---------------------------------------------------------------


class TrabajadorCreate(BaseModel):
    empresa_id: uuid.UUID
    persona_id: uuid.UUID
    cargo: str = Field(max_length=100)
    area: str = Field(max_length=100)
    tipo_vinculo: str
    fecha_ingreso: date
    usuario_id: uuid.UUID | None = None
    regimen_laboral: str | None = None
    remuneracion_base: Decimal | None = None
    sistema_pensiones: str | None = None
    afp_nombre: str | None = None
    tiene_poderes: bool = False
    registra_asistencia: bool = True
    jornada_horas_semana: Decimal | None = None


class TrabajadorUpdate(BaseModel):
    cargo: str | None = None
    area: str | None = None
    remuneracion_base: Decimal | None = None
    estado: str | None = None


class TrabajadorCese(BaseModel):
    fecha_cese: date


class TrabajadorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    persona_id: uuid.UUID
    usuario_id: uuid.UUID | None
    cargo: str
    area: str
    tipo_vinculo: str
    fecha_ingreso: date
    fecha_cese: date | None
    registra_asistencia: bool
    estado: str


# --- Contrato laboral ----------------------------------------------------------


class ContratoLaboralCreate(BaseModel):
    trabajador_id: uuid.UUID
    modalidad: str
    jornada_horas_semana: Decimal = Field(gt=0)
    remuneracion: Decimal = Field(gt=0)
    fecha_inicio: date
    fecha_fin: date | None = None


class ContratoLaboralFirmar(BaseModel):
    fecha_firma: date


class ContratoLaboralOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    trabajador_id: uuid.UUID
    modalidad: str
    remuneracion: Decimal
    fecha_inicio: date
    fecha_fin: date | None
    estado: str
    fecha_firma: date | None


# --- Postulante -----------------------------------------------------------------


class PostulanteCreate(BaseModel):
    persona_id: uuid.UUID
    puesto_postulado: str = Field(max_length=150)
    fecha_postulacion: date
    consentimiento_datos: bool
    consentimiento_fecha: date | None = None
    plazo_conservacion_declarado: date | None = None
    cv_archivo_id: uuid.UUID | None = None


class PostulanteEstado(BaseModel):
    estado: str


class PostulanteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    persona_id: uuid.UUID
    puesto_postulado: str
    fecha_postulacion: date
    consentimiento_datos: bool
    estado: str


# --- Socio -----------------------------------------------------------------------


class SocioCreate(BaseModel):
    porcentaje_participacion: Decimal = Field(gt=0, le=100)
    grupo_id: uuid.UUID | None = None
    empresa_id: uuid.UUID | None = None
    persona_id: uuid.UUID | None = None
    razon_social: str | None = Field(default=None, max_length=255)
    ruc: str | None = Field(default=None, min_length=11, max_length=11)


class SocioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    grupo_id: uuid.UUID | None
    empresa_id: uuid.UUID | None
    persona_id: uuid.UUID | None
    razon_social: str | None
    ruc: str | None
    porcentaje_participacion: Decimal


# --- Nómina ------------------------------------------------------------------


class BoletaPagoCreate(BaseModel):
    trabajador_id: uuid.UUID
    periodo: str = Field(min_length=7, max_length=7)
    dias_laborados: int = Field(ge=0, le=31)
    remuneracion: Decimal = Field(ge=0)
    ingresos: dict
    descuentos: dict
    aportes_empleador: Decimal = Field(ge=0)
    neto_pagar: Decimal = Field(ge=0)
    fecha_pago: date
    idempotency_key: str = Field(min_length=8, max_length=100)


class BoletaPagoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    trabajador_id: uuid.UUID
    periodo: str
    neto_pagar: Decimal
    fecha_pago: date


class LiquidacionBssCreate(BaseModel):
    trabajador_id: uuid.UUID
    cts_pendiente: Decimal = Field(default=Decimal(0), ge=0)
    vacaciones_truncas: Decimal = Field(default=Decimal(0), ge=0)
    gratificacion_trunca: Decimal = Field(default=Decimal(0), ge=0)
    otros_adeudos: Decimal = Field(default=Decimal(0), ge=0)
    fecha_pago: date
    idempotency_key: str = Field(min_length=8, max_length=100)


class LiquidacionBssOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    trabajador_id: uuid.UUID
    total: Decimal
    fecha_pago: date
    dentro_de_plazo: bool


# --- Disciplina y documentos -----------------------------------------------------


class MemorandumCreate(BaseModel):
    empresa_id: uuid.UUID
    emisor_id: uuid.UUID
    asunto: str = Field(max_length=200)
    cuerpo: str
    fecha: date
    destinatario_trabajador_id: uuid.UUID | None = None
    destinatario_area: str | None = Field(default=None, max_length=100)


class MemorandumOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    asunto: str
    fecha: date


class AmonestacionCreate(BaseModel):
    trabajador_id: uuid.UUID
    tipo: str
    falta: str
    fecha_hecho: date
    fecha_emision: date
    emisor_id: uuid.UUID
    descargo: str | None = None
    descargo_plazo_dias: int | None = None
    sancion_relacionada: str | None = None


class AmonestacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    trabajador_id: uuid.UUID
    tipo: str
    fecha_emision: date


class ActaCreate(BaseModel):
    empresa_id: uuid.UUID
    tipo: str
    fecha: date
    lugar: str = Field(max_length=200)
    hechos: str
    participantes: list[dict]


class ActaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    tipo: str
    fecha: date


class CertificadoTrabajoCreate(BaseModel):
    trabajador_id: uuid.UUID
    fecha_emision: date
    cargos: str = Field(max_length=255)
    conducta_desempeno: str | None = None


class CertificadoTrabajoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    trabajador_id: uuid.UUID
    fecha_emision: date
    tiempo_servicios_meses: int
    dentro_de_plazo: bool


# --- Permisos ------------------------------------------------------------------


class SolicitudPermisoCreate(BaseModel):
    trabajador_id: uuid.UUID
    tipo: str
    fecha_desde: date
    fecha_hasta: date | None = None
    horas: Decimal | None = None
    motivo: str | None = None


class SolicitudPermisoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    trabajador_id: uuid.UUID
    tipo: str
    fecha_desde: date
    fecha_hasta: date | None
    estado: str
    aprobador_id: uuid.UUID | None


# --- Capacitación --------------------------------------------------------------


class PactoPermanenciaCreate(BaseModel):
    trabajador_id: uuid.UUID
    capacitacion_descripcion: str = Field(max_length=255)
    capacitacion_tipo: str
    costo_financiado: Decimal = Field(gt=0)
    plazo_permanencia_meses: int = Field(gt=0)
    fecha_inicio: date
    fecha_fin_compromiso: date


class PactoPermanenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    trabajador_id: uuid.UUID
    costo_financiado: Decimal
    plazo_permanencia_meses: int


# --- Asistencia ------------------------------------------------------------------


class AsistenciaMarcarEntrada(BaseModel):
    trabajador_id: uuid.UUID
    fecha: date
    hora_entrada: time
    tardanza_min: int = 0


class AsistenciaMarcarSalida(BaseModel):
    trabajador_id: uuid.UUID
    fecha: date
    hora_salida: time
    horas_extra: Decimal = Decimal(0)


class AsistenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    trabajador_id: uuid.UUID
    fecha: date
    hora_entrada: time | None
    hora_salida: time | None
    tardanza_min: int
    horas_extra: Decimal
