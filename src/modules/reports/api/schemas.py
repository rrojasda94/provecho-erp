"""Esquemas de entrada/salida del módulo `reports`."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TipoDestinatario = Literal["area", "rol", "usuario", "dinamico"]
Nivel = Literal["info", "aviso", "urgente"]
Canal = Literal["bandeja"]

# Cómo se nombra al actor de un hecho que no provocó nadie. Se muestra igual
# que un nombre de usuario para que la ficha nunca tenga un hueco (RN-REP-009).
ACTOR_SISTEMA = "Sistema"


# --- Catálogo -----------------------------------------------------------------
class EmisionOut(BaseModel):
    codigo: str
    nombre: str
    descripcion: str
    permiso: str
    nivel: str
    ambito: str
    campos: list[str]
    areas_sugeridas: list[str]
    dinamicos_sugeridos: list[str]
    referencia_tipo: str


class DestinoOut(BaseModel):
    """A dónde lleva un `referencia_tipo` y con qué permiso (ADR-036)."""

    ruta: str
    permiso: str
    etiqueta: str


class CatalogoEmisionesOut(BaseModel):
    emisiones: list[EmisionOut]
    # El frontend no repite estas listas ni las traduce por su cuenta.
    niveles: list[str]
    dinamicos: list[str]
    # `referencia_tipo` → destino. Va acá y no en cada reporte para que el
    # cliente sepa qué permiso exige el botón antes de dibujarlo: un enlace
    # visible para todos lleva a un 403 (RN-REP-002).
    destinos: dict[str, DestinoOut] = Field(default_factory=dict)


# --- Áreas --------------------------------------------------------------------
class AreaCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=30, pattern=r"^[a-z][a-z0-9_]*$")
    nombre: str = Field(min_length=1, max_length=100)
    # Viene del JWT; se acepta explícito solo para el superusuario de setup.
    empresa_id: uuid.UUID | None = None


class AreaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    activa: bool | None = None


class AreaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    empresa_id: uuid.UUID
    codigo: str
    nombre: str
    activa: bool


class MiembroCreate(BaseModel):
    rol_id: uuid.UUID | None = None
    usuario_id: uuid.UUID | None = None
    # Acota la membresía a un local. Nulo = toda la empresa.
    sucursal_id: uuid.UUID | None = None


class MiembroOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    area_id: uuid.UUID
    rol_id: uuid.UUID | None
    usuario_id: uuid.UUID | None
    sucursal_id: uuid.UUID | None


# --- Reglas -------------------------------------------------------------------
class DestinatarioIn(BaseModel):
    tipo: TipoDestinatario
    area_id: uuid.UUID | None = None
    rol_id: uuid.UUID | None = None
    usuario_id: uuid.UUID | None = None
    dinamico: str | None = Field(default=None, max_length=40)


class DestinatarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: str
    area_id: uuid.UUID | None
    rol_id: uuid.UUID | None
    usuario_id: uuid.UUID | None
    dinamico: str | None


class ReglaCreate(BaseModel):
    codigo_emision: str = Field(min_length=1, max_length=60)
    # Nulo = la regla general de la empresa (RN-REP-008).
    sucursal_id: uuid.UUID | None = None
    nivel: Nivel = "aviso"
    canal: Canal = "bandeja"
    activa: bool = True
    destinatarios: list[DestinatarioIn] = Field(default_factory=list, max_length=50)
    empresa_id: uuid.UUID | None = None


class ReglaUpdate(BaseModel):
    nivel: Nivel | None = None
    canal: Canal | None = None
    activa: bool | None = None
    # `None` deja los destinatarios como están; una lista los reemplaza en
    # bloque (incluida la vacía, que deja la regla sin destinatarios).
    destinatarios: list[DestinatarioIn] | None = Field(default=None, max_length=50)


class ReglaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    empresa_id: uuid.UUID
    codigo_emision: str
    sucursal_id: uuid.UUID | None
    activa: bool
    nivel: str
    canal: str
    destinatarios: list[DestinatarioOut] = Field(default_factory=list)


# --- Matriz -------------------------------------------------------------------
class MatrizDestinatarioOut(BaseModel):
    tipo: str
    id: str | None
    etiqueta: str


class MatrizReglaOut(BaseModel):
    id: str
    sucursal_id: str | None
    sucursal: str
    activa: bool
    nivel: str
    canal: str
    destinatarios: list[MatrizDestinatarioOut]
    # Cuántas personas alcanza hoy, sin contar resolutores dinámicos.
    alcance: int
    # Regla activa que no llega a nadie.
    fuga: bool


class MatrizFilaOut(BaseModel):
    codigo: str
    nombre: str
    descripcion: str
    permiso: str
    nivel: str
    ambito: str
    areas_sugeridas: list[str]
    reglas: list[MatrizReglaOut]
    # El hecho ocurre y no se entera nadie: no hay ninguna regla activa.
    hueco: bool


# --- Reportes emitidos --------------------------------------------------------
class ReporteEmitidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    empresa_id: uuid.UUID | None
    sucursal_id: uuid.UUID | None
    almacen_id: uuid.UUID | None
    codigo_emision: str
    titulo: str
    cuerpo: str | None
    nivel: str
    referencia_tipo: str | None
    referencia_id: uuid.UUID | None
    emitido_at: datetime
    # El endpoint donde se mira —y se resuelve— el hecho. Nulo cuando el
    # reporte no apunta a ninguna entidad.
    referencia_url: str | None = None
    # Quién provocó el hecho. Nulo con `actor = "Sistema"` cuando lo detectó
    # un barrido y no hay a quién atribuírselo (RN-REP-009). Se resuelve
    # aparte del ORM, así que lleva default.
    actor_id: uuid.UUID | None = None
    actor: str = ACTOR_SISTEMA


class EntregaReporteOut(BaseModel):
    usuario_id: uuid.UUID
    usuario: str
    # `area:almacen`, `rol:supervisor`, `dinamico:encargado_de_turno`.
    motivo: str
    canal: str


# --- Escalamiento (ADR-036) ---------------------------------------------------
MotivoEscalamiento = Literal[
    "queja",
    "demora",
    "error_sistema",
    "desistimiento_no_resuelto",
    "no_conformidad_calidad",
]


class EscalamientoCreate(BaseModel):
    motivo: MotivoEscalamiento
    descripcion: str = Field(min_length=1, max_length=2000)
    # Obligatoria si el motivo es no conformidad y la orden terminó en desecho
    # (RN-PRD-015). Lo valida el caso de uso contra la foto del reporte.
    evidencia_id: uuid.UUID | None = None


class AccionEscalamientoIn(BaseModel):
    descripcion: str = Field(min_length=1, max_length=2000)


class EscalamientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    empresa_id: uuid.UUID
    sucursal_id: uuid.UUID | None
    reporte_emitido_id: uuid.UUID
    origen: str
    motivo: str
    descripcion: str
    reportado_por_id: uuid.UUID
    evidencia_id: uuid.UUID | None
    nivel_actual: str
    estado: str
    cerrado_at: datetime | None
    created_at: datetime


class EscalamientoDetalleOut(EscalamientoOut):
    # El historial por nivel: quién, qué y cuándo. Append-only (RN-REP-012).
    acciones: list[dict[str, Any]] = Field(default_factory=list)
    # A quiénes le llegó el aviso de esta elevación. Vacío no es un error: la
    # emisión se guarda igual y sale como fuga en la matriz (RN-REP-005). Que
    # se vea es el punto — quien eleva tiene que saber si llegó a alguien.
    destinatarios: list[str] = Field(default_factory=list)


class ReporteEmitidoDetalleOut(ReporteEmitidoOut):
    # La foto de los campos declarados por la emisión (RN-REP-003).
    datos: dict[str, Any]
    regla_id: uuid.UUID | None
    # Se llena aparte del ORM (necesita el nombre de cada usuario), así que
    # tiene default: si no, validar el modelo desde la fila fallaría por un
    # campo que todavía no se calculó.
    entregas: list[EntregaReporteOut] = Field(default_factory=list)
