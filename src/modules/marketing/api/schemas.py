"""DTOs (pydantic) del módulo marketing."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TipoCampana = Literal["notoriedad", "impulso_venta", "lanzamiento", "medios", "evento"]
TipoLead = Literal["contacto", "visita", "cupon", "registro"]
CanalEncuesta = Literal["pos", "whatsapp", "link"]
TipoPregunta = Literal["escala", "opcion", "si_no", "texto"]
TipoOpcionAgencia = Literal["agencia", "interna"]


class CampanaCreate(BaseModel):
    marca_id: uuid.UUID
    nombre: str = Field(min_length=3, max_length=120)
    tipo: TipoCampana
    canal: str = Field(min_length=2, max_length=50)
    objetivo: str | None = Field(default=None, max_length=255)
    publico_objetivo: str | None = Field(default=None, max_length=255)
    presupuesto: Decimal | None = Field(default=None, ge=0)
    kpi: str | None = Field(default=None, max_length=255)
    idempotency_key: str = Field(min_length=8, max_length=100)
    # Solo lo usa un superusuario sin empresa asignada (ADR-004).
    empresa_id: uuid.UUID | None = None


class BriefUpdate(BaseModel):
    objetivo: str | None = Field(default=None, max_length=255)
    publico_objetivo: str | None = Field(default=None, max_length=255)
    presupuesto: Decimal | None = Field(default=None, ge=0)
    kpi: str | None = Field(default=None, max_length=255)


class CampanaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    marca_id: uuid.UUID
    nombre: str
    tipo: str
    canal: str
    objetivo: str | None
    publico_objetivo: str | None
    presupuesto: Decimal | None
    kpi: str | None
    estado: str
    aprobada_por: uuid.UUID | None


class ImplementacionCreate(BaseModel):
    sucursal_id: uuid.UUID
    completa: bool
    incidencia: str | None = Field(default=None, max_length=255)
    fecha: date | None = None


class ImplementacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    campana_id: uuid.UUID
    sucursal_id: uuid.UUID
    fecha: date
    completa: bool
    incidencia: str | None


class PiezaCreate(BaseModel):
    marca_id: uuid.UUID
    titulo: str = Field(min_length=3, max_length=150)
    canal: str = Field(min_length=2, max_length=50)
    fecha_publicacion: date
    campana_id: uuid.UUID | None = None
    pertinente_marca: bool = False
    uso_marca_validado: bool = False


class PiezaValidar(BaseModel):
    pertinente_marca: bool | None = None
    uso_marca_validado: bool | None = None


class PiezaPublicar(BaseModel):
    metricas: dict | None = None


class PiezaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    campana_id: uuid.UUID | None
    marca_id: uuid.UUID
    titulo: str
    canal: str
    fecha_publicacion: date
    pertinente_marca: bool
    uso_marca_validado: bool
    estado: str
    metricas: dict | None


class LeadCreate(BaseModel):
    campana_id: uuid.UUID
    canal: str = Field(min_length=2, max_length=50)
    tipo: TipoLead
    contacto: str | None = Field(default=None, max_length=120)
    cliente_id: uuid.UUID | None = None
    idempotency_key: str = Field(min_length=8, max_length=100)


class LeadAtribuir(BaseModel):
    venta_id: uuid.UUID


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    campana_id: uuid.UUID
    canal: str
    tipo: str
    contacto: str | None
    cliente_id: uuid.UUID | None
    venta_id: uuid.UUID | None


class EncuestaCreate(BaseModel):
    venta_id: uuid.UUID
    canal: CanalEncuesta
    # Sin plantilla explícita se usa la activa de la empresa.
    plantilla_id: uuid.UUID | None = None


class EncuestaRespuesta(BaseModel):
    """Respuesta a **un nodo**, no a la encuesta entera: el guion decide cuál
    es la siguiente pregunta a partir de este valor."""

    valor: str = Field(min_length=1, max_length=500)


class EncuestaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    venta_id: uuid.UUID
    cliente_id: uuid.UUID
    canal: str
    fecha_envio: datetime
    fecha_respuesta: datetime | None
    fecha_expiracion: datetime
    puntaje: int | None
    comentario: str | None
    estado: str
    plantilla_id: uuid.UUID | None
    pregunta_actual_id: uuid.UUID | None
    error_envio: str | None


class PreguntaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    codigo: str
    orden: int
    texto: str
    tipo: TipoPregunta
    opciones: list[dict] | None
    siguiente_codigo: str | None
    saltos: dict | None
    es_puntaje: bool
    obligatoria: bool


class EncuestaConNodoOut(BaseModel):
    """La encuesta y en qué nodo quedó: quien la envía o la contesta necesita
    ver la pregunta pendiente sin pedirla aparte."""

    encuesta: EncuestaOut
    pregunta_actual: PreguntaOut | None
    url_publica: str


class OpcionPregunta(BaseModel):
    valor: str = Field(min_length=1, max_length=30)
    etiqueta: str = Field(min_length=1, max_length=60)


class PreguntaCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=30, pattern=r"^[a-z0-9_]+$")
    texto: str = Field(min_length=3, max_length=300)
    tipo: TipoPregunta
    opciones: list[OpcionPregunta] | None = None
    siguiente_codigo: str | None = Field(default=None, max_length=30)
    saltos: dict[str, str] | None = None
    es_puntaje: bool = False
    obligatoria: bool = True


class PlantillaCreate(BaseModel):
    nombre: str = Field(min_length=3, max_length=120)
    saludo: str = Field(min_length=3, max_length=300)
    despedida: str = Field(default="¡Gracias por responder!", max_length=300)
    preguntas: list[PreguntaCreate] = Field(min_length=1)
    marca_id: uuid.UUID | None = None
    activa: bool = False
    # Solo lo usa un superusuario sin empresa asignada (ADR-004).
    empresa_id: uuid.UUID | None = None


class PlantillaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    marca_id: uuid.UUID | None
    nombre: str
    saludo: str
    despedida: str
    activa: bool


class PlantillaDetalleOut(PlantillaOut):
    preguntas: list[PreguntaOut]


# --- Encuesta pública (sin autenticación) -----------------------------------


class PreguntaPublicaOut(BaseModel):
    codigo: str
    texto: str
    tipo: TipoPregunta
    opciones: list[OpcionPregunta]
    obligatoria: bool


class NodoPublicoOut(BaseModel):
    """Lo mínimo para pintar la pregunta al cliente. Nunca incluye la venta,
    el cliente ni el puntaje ya dado: el token es una credencial anónima y
    lo que devuelve no puede filtrar datos del pedido."""

    estado: str
    saludo: str
    terminada: bool
    mensaje: str
    pregunta: PreguntaPublicaOut | None


class RespuestaPublicaIn(BaseModel):
    valor: str = Field(min_length=1, max_length=500)


# --- Adjuntos de contenido ---------------------------------------------------


class AdjuntoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=3, max_length=100)
    tamano_bytes: int = Field(gt=0)
    url_storage: str = Field(min_length=3, max_length=500)


class AdjuntoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    extension: str
    mime_type: str
    tamano_bytes: int
    url_storage: str


class PiezaCalendarioOut(PiezaOut):
    adjuntos: int


class DiaCalendarioOut(BaseModel):
    fecha: date
    piezas: list[PiezaCalendarioOut]


class CalendarioOut(BaseModel):
    desde: date
    hasta: date
    dias: list[DiaCalendarioOut]


# --- Evaluación de agencia (RN-MKT-006) --------------------------------------


class CriterioIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=30, pattern=r"^[a-z0-9_]+$")
    etiqueta: str = Field(min_length=1, max_length=80)
    peso: Decimal = Field(gt=0, le=100)


class EvaluacionCreate(BaseModel):
    objetivo: str = Field(min_length=3, max_length=255)
    presupuesto_referencia: Decimal = Field(gt=0)
    criterios: list[CriterioIn] = Field(min_length=1)


class OpcionCreate(BaseModel):
    tipo: TipoOpcionAgencia
    nombre: str = Field(min_length=2, max_length=150)
    costo: Decimal = Field(ge=0)
    plazo_dias: int = Field(gt=0)
    puntajes: dict[str, int]
    proveedor_id: uuid.UUID | None = None
    observacion: str | None = Field(default=None, max_length=500)


class DecisionAgencia(BaseModel):
    opcion_id: uuid.UUID
    motivo: str | None = Field(default=None, max_length=500)


class OpcionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    evaluacion_id: uuid.UUID
    tipo: str
    nombre: str
    proveedor_id: uuid.UUID | None
    costo: Decimal
    plazo_dias: int
    puntajes: dict
    puntaje_total: Decimal
    observacion: str | None


class EvaluacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    campana_id: uuid.UUID
    objetivo: str
    presupuesto_referencia: Decimal
    criterios: list
    estado: str
    opcion_elegida_id: uuid.UUID | None
    decidida_por: uuid.UUID | None
    fecha_decision: datetime | None
    motivo: str | None
    opciones: list[OpcionOut]


class EvaluacionConSugerenciaOut(BaseModel):
    evaluacion: EvaluacionOut
    # Cuál gana con los criterios declarados. Gerencia puede apartarse, pero
    # entonces el motivo pasa a ser obligatorio.
    opcion_recomendada_id: uuid.UUID | None


# --- Métricas de campaña -----------------------------------------------------


class MetricaCampanaOut(BaseModel):
    campana_id: uuid.UUID
    fecha_lanzamiento: date | None
    leads_generados: int
    leads_convertidos: int
    piezas_publicadas: int
    encuestas_enviadas: int
    encuestas_respondidas: int
    tasa_conversion: float | None
    puntaje_promedio: float | None
