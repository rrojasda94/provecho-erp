"""DTOs (pydantic) del módulo production."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrdenProduccionCreate(BaseModel):
    articulo_id: uuid.UUID
    almacen_id: uuid.UUID
    cantidad_planeada: Decimal = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=100)


class OrdenProduccionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    articulo_id: uuid.UUID
    almacen_id: uuid.UUID
    plan_produccion_id: uuid.UUID | None = None
    orden_padre_id: uuid.UUID | None = None
    origen: str = "manual"
    cantidad_planeada: Decimal
    cantidad_producida: Decimal | None
    estado: str
    costo_teorico_insumos: Decimal | None = None
    costo_insumos: Decimal | None
    horas_hombre: Decimal | None = None
    costo_mano_obra: Decimal | None
    costo_real_unitario: Decimal | None
    merma_cantidad: Decimal | None
    merma_motivo: str | None
    evidencia_archivo_id: uuid.UUID | None = None
    fecha_vencimiento: date | None
    lote_codigo: str | None
    trazabilidad: dict | None


class EvidenciaCreate(BaseModel):
    """Evidencia de destrucción ya subida al storage — mismo contrato que
    `marketing.AdjuntoCreate` (RN-PRD-015)."""

    nombre: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=3, max_length=100)
    tamano_bytes: int = Field(gt=0)
    url_storage: str = Field(min_length=3, max_length=500)


class EvidenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    extension: str
    mime_type: str
    tamano_bytes: int
    url_storage: str


class ConsumoProduccionItemOut(BaseModel):
    id: uuid.UUID
    articulo_id: uuid.UUID
    cantidad: Decimal
    unidad_medida_id: uuid.UUID | None
    costo_unitario: Decimal
    peso_desperdicio_real: Decimal
    tipo_desperdicio: str | None
    # Real menos lo que la receta espera por `merma_pct` (RN-PRD-018). `None`
    # si el artículo no tiene receta con la que contrastar.
    desviacion_desperdicio: Decimal | None


class TrabajadorHorasOut(BaseModel):
    trabajador_id: uuid.UUID
    horas: Decimal


class TrabajadorDisponibleOut(BaseModel):
    """Para el picker del diálogo de completar — mismo shape que devuelve
    `rrhh.queries_publicas.trabajadores_activos`."""

    id: uuid.UUID
    nombre: str
    cargo: str


class OrdenHijaResumenOut(BaseModel):
    """Lo mínimo para el árbol padre/hijas de la ficha — no la orden
    entera, que ya se puede pedir aparte por `GET /ordenes/{id}`."""

    id: uuid.UUID
    articulo_id: uuid.UUID
    estado: str
    cantidad_planeada: Decimal
    cantidad_producida: Decimal | None


class OrdenProduccionDetalleOut(OrdenProduccionOut):
    consumos: list[ConsumoProduccionItemOut]
    trabajadores: list[TrabajadorHorasOut]
    hijas: list[OrdenHijaResumenOut]


class OrdenHijaCreate(BaseModel):
    articulo_id: uuid.UUID
    cantidad_planeada: Decimal = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=100)


class ConsumoSugeridoLineaOut(BaseModel):
    articulo_id: uuid.UUID
    articulo_nombre: str
    unidad_medida_id: uuid.UUID | None
    unidad_medida_nombre: str | None
    merma_pct: Decimal
    cantidad_sugerida: Decimal
    desperdicio_esperado: Decimal
    costo_unitario: Decimal
    costo_linea: Decimal
    # RN-PRD-020: el artículo tiene receta BOM propia y el almacén no tiene
    # disponible para cubrir `cantidad_sugerida` — hay que fabricarlo antes
    # con `POST /ordenes/{id}/ordenes-hijas`.
    requiere_orden_hija: bool


class ConsumoSugeridoOut(BaseModel):
    receta_id: uuid.UUID
    rendimiento_cantidad: Decimal
    factor: Decimal
    items: list[ConsumoSugeridoLineaOut]
    costo_total: Decimal


class ConsumoItemIn(BaseModel):
    articulo_id: uuid.UUID
    cantidad: Decimal = Field(gt=0)
    # Opcional desde `feat/produccion-costeo-real`: sin ella, se costea al
    # `costo_promedio` vigente del artículo en vez de que quien registra el
    # consumo lo tipee sin ninguna referencia (RN-PRD-018).
    costo_unitario: Decimal | None = Field(default=None, ge=0)
    # Opcional: la UdM en la que se tecleó `cantidad`, si no es la del
    # artículo (RN-UDM-005, ej. gramos sobre un insumo que se lleva en
    # kilos). `None` = la del artículo, sin conversión.
    unidad_medida_id: uuid.UUID | None = None
    peso_desperdicio_real: Decimal = Decimal(0)
    tipo_desperdicio: str | None = None


class ConsumoCreate(BaseModel):
    items: list[ConsumoItemIn] = Field(min_length=1)
    # Opcional: sin ella, un reintento de red puede duplicar el consumo
    # (deuda técnica, ver ROADMAP). Con la misma clave, la segunda llamada
    # devuelve la orden tal como quedó, sin volver a procesar nada.
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)


class TrabajadorHorasIn(BaseModel):
    trabajador_id: uuid.UUID
    # Opcional: sin ella, se imputan todas las horas que el trabajador
    # asistió hoy (`rrhh.queries_publicas.horas_asistidas`). Si viene, no
    # puede superar lo asistido (RN-RRHH-009, 409).
    horas: Decimal | None = Field(default=None, gt=0)


class CompletarOrdenIn(BaseModel):
    resultado: str
    cantidad_producida: Decimal | None = Field(default=None, gt=0)
    # Reemplaza al `horas_hombre` tipeado a mano (RN-PRD-018): cada
    # trabajador imputado aporta su asistencia real del día, no un número
    # que nadie podía contrastar contra nada. Vacío = sin mano de obra
    # imputada (`horas_hombre` de la orden queda en 0), igual que antes.
    trabajadores: list[TrabajadorHorasIn] = Field(default_factory=list)
    merma_cantidad: Decimal | None = Field(default=None, gt=0)
    merma_motivo: str | None = None
    # Ya no viaja acá: la evidencia de destrucción (RN-PRD-015) se sube
    # antes vía `POST /ordenes/{id}/evidencia` — `completar` solo exige que
    # ya exista (`orden.evidencia_archivo_id`).
    # Trazabilidad del lote (RN-LOT-002/003, RN-VNC-001): solo tiene efecto
    # cuando `resultado="conforme"` — es lo que produce el lote del producto
    # terminado. Sin `fecha_vencimiento` el lote nace sin vencimiento y FEFO
    # lo trata como FIFO (deuda técnica ya cerrada por este bloque).
    fecha_vencimiento: date | None = None
    lote_codigo: str | None = Field(default=None, max_length=50)
    trazabilidad: dict | None = None
    # Mismo criterio que en `ConsumoCreate`.
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)


class PlanProduccionCreate(BaseModel):
    almacen_id: uuid.UUID
    fecha: date
    turno: str = Field(min_length=1, max_length=30)
    linea_produccion: str = Field(min_length=1, max_length=100)


class PlanProduccionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    almacen_id: uuid.UUID
    fecha: date
    turno: str
    linea_produccion: str
    origen: str
    estado: str


class AgregarOrdenAPlanIn(BaseModel):
    articulo_id: uuid.UUID
    cantidad_planeada: Decimal = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=100)


class EquipoFrioIn(BaseModel):
    """Sin `dentro_rango`: lo calcula el servidor a partir de la
    temperatura y el rango — nunca lo decide quien registra el checklist."""

    equipo: str = Field(min_length=1, max_length=100)
    temperatura_c: Decimal
    rango_min: Decimal
    rango_max: Decimal


class EquipoFrioOut(EquipoFrioIn):
    dentro_rango: bool


class ChecklistInocuidadTurnoCreate(BaseModel):
    almacen_id: uuid.UUID
    fecha: date
    turno: str = Field(min_length=1, max_length=30)
    bioseguridad_ok: bool
    superficies_ok: bool
    limpieza_intermedia_ok: bool
    equipos_frio: list[EquipoFrioIn] = Field(default_factory=list)
    plaga_indicio: bool = False


class ChecklistInocuidadTurnoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    almacen_id: uuid.UUID
    fecha: date
    turno: str
    verificado_por: uuid.UUID
    bioseguridad_ok: bool
    superficies_ok: bool
    limpieza_intermedia_ok: bool
    equipos_frio: list[EquipoFrioOut]
    plaga_indicio: bool
    estado: str


class GenerarReporteJornadaIn(BaseModel):
    almacen_id: uuid.UUID
    # Opcional: sin ella, la jornada de hoy (`fechas.hoy()`).
    fecha: date | None = None


class VisarReporteJornadaIn(BaseModel):
    observaciones: str | None = Field(default=None, max_length=1000)


class OrdenDeJornadaOut(BaseModel):
    orden_produccion_id: uuid.UUID
    articulo_id: uuid.UUID
    estado: str
    cantidad_producida: Decimal | None
    costo_real_unitario: Decimal | None
    merma_cantidad: Decimal | None
    horas_hombre: Decimal | None


class ReporteProduccionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    almacen_id: uuid.UUID
    jornada: date
    generado_at: datetime
    ordenes: list[OrdenDeJornadaOut]
    merma_total: Decimal
    desperdicio_total: Decimal
    horas_hombre_total: Decimal
    costo_total: Decimal
    visado_por: uuid.UUID | None
    visado_at: datetime | None
    observaciones: str | None
