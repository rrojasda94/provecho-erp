"""DTOs (pydantic) del módulo rrhh."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- Trabajador ---------------------------------------------------------------


class TrabajadorCreate(BaseModel):
    # `empresa_id` sale del JWT (ADR-004). Solo un superusuario sin empresa
    # asignada puede indicarla.
    empresa_id: uuid.UUID | None = None
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
    # Centro de labores (ADR-062). Opcional: gerencia no está en un local.
    sucursal_id: uuid.UUID | None = None


class TrabajadorUpdate(BaseModel):
    """Campo ausente = no tocar.

    `sucursal_id` y `usuario_id` son la excepción: mandarlos en `null`
    **borran** el valor, porque quedarse sin local asignado —o sin cuenta— es
    un estado válido y no había otra forma de volver a él. Para el resto,
    `null` sigue siendo "no tocar".

    `usuario_id` faltaba acá y era la razón por la que nadie podía marcar en
    el pad de asistencia: `TrabajadorCreate` sí lo aceptaba, pero un
    trabajador ya dado de alta no tenía ninguna forma de recibir su cuenta, y
    `pad_asistencia.usuario_que_firma` exige justamente ese campo para llegar
    al PIN.

    `estado` no admite `"cesado"`: el cese tiene su propio endpoint
    (`POST /trabajadores/{id}/cesar`) porque además de cambiar el estado
    fija la fecha de cese y publica el evento del que cuelga la liquidación.
    Llegar a `cesado` por este PATCH dejaba un trabajador cesado sin fecha
    y sin que nadie se enterara.
    """

    cargo: str | None = Field(default=None, min_length=1, max_length=100)
    area: str | None = Field(default=None, min_length=1, max_length=100)
    remuneracion_base: Decimal | None = Field(default=None, ge=0)
    estado: Literal["activo", "suspendido"] | None = None
    sucursal_id: uuid.UUID | None = None
    usuario_id: uuid.UUID | None = None


class TrabajadorCese(BaseModel):
    fecha_cese: date


class TrabajadorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    persona_id: uuid.UUID
    usuario_id: uuid.UUID | None
    sucursal_id: uuid.UUID | None
    cargo: str
    area: str
    tipo_vinculo: str
    fecha_ingreso: date
    fecha_cese: date | None
    # Viaja para que el formulario de corrección pueda precargarla: sin esto
    # editar el cargo obligaba a reteclear la remuneración de memoria.
    remuneracion_base: Decimal | None
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


# --- Convocatoria ----------------------------------------------------------------


class ConvocatoriaCreate(BaseModel):
    # `empresa_id` sale del JWT (ADR-004). Solo un superusuario sin empresa
    # asignada puede indicarla.
    empresa_id: uuid.UUID | None = None
    sucursal_id: uuid.UUID | None = None
    puesto: str = Field(max_length=150)
    motivo: str
    perfil_puesto: str | None = Field(default=None, max_length=100)
    vacantes: int = Field(default=1, ge=1, le=99)
    jornada_horas_semana: Decimal | None = Field(default=None, gt=0, le=48)
    remuneracion_min: Decimal | None = Field(default=None, ge=0)
    remuneracion_max: Decimal | None = Field(default=None, ge=0)
    fecha_objetivo: date | None = None
    fecha_limite: date | None = None


class ConvocatoriaPublicar(BaseModel):
    fecha_publicacion: date
    # Permite adjuntar el perfil aprobado en el mismo paso de publicar.
    perfil_puesto: str | None = Field(default=None, max_length=100)


class ConvocatoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    sucursal_id: uuid.UUID | None
    puesto: str
    motivo: str
    perfil_puesto: str | None
    vacantes: int
    remuneracion_min: Decimal | None
    remuneracion_max: Decimal | None
    fecha_objetivo: date | None
    fecha_limite: date | None
    fecha_publicacion: date | None
    # Lo necesita quien arma la URL del formulario público.
    token_publico: str | None
    estado: str


# --- Postulante -----------------------------------------------------------------

_MAX_RESPUESTAS = 40
_MAX_LARGO_RESPUESTA = 2000


def _valida_respuestas(v: dict[str, str] | None) -> dict[str, str] | None:
    """El formulario es de terceros y el endpoint que lo recibe es público:
    lo que entra se acota acá o no se acota en ninguna parte."""
    if v is None:
        return v
    if len(v) > _MAX_RESPUESTAS:
        raise ValueError(f"máximo {_MAX_RESPUESTAS} respuestas")
    for pregunta, respuesta in v.items():
        if len(pregunta) > 200 or len(respuesta) > _MAX_LARGO_RESPUESTA:
            raise ValueError("pregunta o respuesta demasiado larga")
    return v


class PostulanteCreate(BaseModel):
    # `empresa_id` sale del JWT (ADR-004). Solo un superusuario sin empresa
    # asignada puede indicarla.
    empresa_id: uuid.UUID | None = None
    nombres: str = Field(min_length=1, max_length=100)
    apellidos: str = Field(min_length=1, max_length=100)
    puesto_postulado: str = Field(max_length=150)
    fecha_postulacion: date
    consentimiento_datos: bool
    convocatoria_id: uuid.UUID | None = None
    telefono: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=150)
    canal_origen: str | None = Field(default=None, max_length=50)
    respuestas: dict[str, str] | None = None
    consentimiento_fecha: date | None = None
    plazo_conservacion_declarado: date | None = None
    cv_archivo_id: uuid.UUID | None = None

    _respuestas_acotadas = field_validator("respuestas")(_valida_respuestas)


class PostulacionPublica(BaseModel):
    """Cuerpo del formulario público. Sin `fecha_postulacion`: la pone el
    servidor, si no el cliente podría postular fuera de la fecha límite."""

    nombres: str = Field(min_length=1, max_length=100)
    apellidos: str = Field(min_length=1, max_length=100)
    consentimiento_datos: bool
    telefono: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=150)
    canal_origen: str | None = Field(default=None, max_length=50)
    respuestas: dict[str, str] | None = None

    _respuestas_acotadas = field_validator("respuestas")(_valida_respuestas)


class PostulanteUpdate(BaseModel):
    """Rectificación (ARCO): solo datos de contacto. El puesto, el estado y
    el motivo de descarte no son 'datos del titular' que él pueda corregir."""

    nombres: str | None = Field(default=None, min_length=1, max_length=100)
    apellidos: str | None = Field(default=None, min_length=1, max_length=100)
    telefono: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=150)


class PostulanteAnonimizar(BaseModel):
    motivo: str = Field(min_length=1, max_length=255)


class PostulanteAvanzar(BaseModel):
    estado: str


class PostulanteDescartar(BaseModel):
    motivo: str = Field(min_length=1, max_length=255)


class PostulanteContratar(BaseModel):
    cargo: str = Field(max_length=100)
    area: str = Field(max_length=100)
    tipo_vinculo: str
    fecha_ingreso: date
    tipo_documento: str | None = None
    numero_documento: str | None = Field(default=None, max_length=20)
    # Corregidos por quien contrata tras verlos contra RENIEC. Opcionales:
    # sin ellos manda lo que el postulante declaró de sí mismo.
    nombres: str | None = Field(default=None, max_length=100)
    apellidos: str | None = Field(default=None, max_length=100)
    # Ex-trabajador recontratado: se reusa su `persona`, no se duplica.
    persona_id: uuid.UUID | None = None
    regimen_laboral: str | None = None
    remuneracion_base: Decimal | None = None
    sistema_pensiones: str | None = None
    afp_nombre: str | None = None
    registra_asistencia: bool = True
    jornada_horas_semana: Decimal | None = None


class PostulanteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    convocatoria_id: uuid.UUID | None
    nombres: str
    apellidos: str
    telefono: str | None
    email: str | None
    puesto_postulado: str
    fecha_postulacion: date
    canal_origen: str | None
    respuestas: dict | None
    consentimiento_datos: bool
    persona_id: uuid.UUID | None
    trabajador_id: uuid.UUID | None
    motivo_descarte: str | None
    plazo_conservacion_declarado: date | None
    anonimizado_at: datetime | None
    estado: str


class TableroColumna(BaseModel):
    estado: str
    postulantes: list[PostulanteOut]


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
    # `empresa_id` sale del JWT (ADR-004). Solo un superusuario sin empresa
    # asignada puede indicarla.
    empresa_id: uuid.UUID | None = None
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
    # `empresa_id` sale del JWT (ADR-004). Solo un superusuario sin empresa
    # asignada puede indicarla.
    empresa_id: uuid.UUID | None = None
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
    turno_id: uuid.UUID | None
    tardanza_min: int
    horas_extra: Decimal


# --- Turno de trabajo ------------------------------------------------------------
class TurnoCreate(BaseModel):
    sucursal_id: uuid.UUID
    nombre: str = Field(max_length=50)
    hora_inicio: time
    hora_fin: time
    hora_limite_salida: time
    tolerancia_min: int = Field(default=5, ge=0, le=120)


class TurnoUpdate(BaseModel):
    nombre: str | None = Field(default=None, max_length=50)
    hora_inicio: time | None = None
    hora_fin: time | None = None
    hora_limite_salida: time | None = None
    tolerancia_min: int | None = Field(default=None, ge=0, le=120)
    activo: bool | None = None


class TurnoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sucursal_id: uuid.UUID
    nombre: str
    hora_inicio: time
    hora_fin: time
    hora_limite_salida: time
    tolerancia_min: int
    activo: bool


# --- Pad de marcación ------------------------------------------------------------
class TarjetaOut(BaseModel):
    """La tarjeta del pad: nombre y nada más. La pantalla está a la vista de
    todo el que pase por la cocina — cargo, documento y sueldo no van acá."""

    model_config = ConfigDict(from_attributes=True)
    trabajador_id: uuid.UUID
    nombre: str
    marco_entrada: bool
    marco_salida: bool


class PadMarcarIn(BaseModel):
    trabajador_id: uuid.UUID
    # Ni fecha ni hora ni tipo: los pone el servidor (ADR-065).
    pin: str = Field(min_length=4, max_length=12)


class PadMarcacionOut(BaseModel):
    tipo: str  # "entrada" | "salida"
    asistencia: AsistenciaOut


# --- Legajo (file personal) ------------------------------------------------------
class LegajoOut(BaseModel):
    """El expediente del trabajador en una sola lectura.

    `nomina_visible` no es decoración: dice si las listas de boletas y
    liquidaciones vinieron vacías porque no hay nada, o porque quien
    pregunta no tiene `rrhh.nomina_gestionar`. Sin ese campo, un legajo sin
    sueldos se lee igual que uno censurado.
    """

    trabajador: TrabajadorOut
    contratos: list[ContratoLaboralOut]
    amonestaciones: list[AmonestacionOut]
    memorandums: list[MemorandumOut]
    certificados: list[CertificadoTrabajoOut]
    permisos: list[SolicitudPermisoOut]
    pactos_permanencia: list[PactoPermanenciaOut]
    nomina_visible: bool
    boletas: list[BoletaPagoOut]
    liquidaciones: list[LiquidacionBssOut]
