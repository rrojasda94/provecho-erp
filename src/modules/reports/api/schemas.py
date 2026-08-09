"""Esquemas de entrada/salida del módulo `reports`."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TipoDestinatario = Literal["area", "rol", "usuario", "dinamico"]
Nivel = Literal["info", "aviso", "urgente"]
Canal = Literal["bandeja"]


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


class CatalogoEmisionesOut(BaseModel):
    emisiones: list[EmisionOut]
    # El frontend no repite estas listas ni las traduce por su cuenta.
    niveles: list[str]
    dinamicos: list[str]


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
    codigo_emision: str
    titulo: str
    cuerpo: str | None
    nivel: str
    referencia_tipo: str | None
    referencia_id: uuid.UUID | None
    emitido_at: datetime


class EntregaReporteOut(BaseModel):
    usuario_id: uuid.UUID
    usuario: str
    # `area:almacen`, `rol:supervisor`, `dinamico:encargado_de_turno`.
    motivo: str
    canal: str


class ReporteEmitidoDetalleOut(ReporteEmitidoOut):
    # La foto de los campos declarados por la emisión (RN-REP-003).
    datos: dict[str, Any]
    regla_id: uuid.UUID | None
    # Se llena aparte del ORM (necesita el nombre de cada usuario), así que
    # tiene default: si no, validar el modelo desde la fila fallaría por un
    # campo que todavía no se calculó.
    entregas: list[EntregaReporteOut] = Field(default_factory=list)
