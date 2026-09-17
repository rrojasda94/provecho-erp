"""DTOs (pydantic) del módulo supervision."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Momento = Literal["apertura", "cierre"]
Frecuencia = Literal["diaria", "interdiaria", "semanal", "mensual"]


class CategoriaCreate(BaseModel):
    empresa_id: uuid.UUID | None = None
    nombre: str = Field(min_length=1, max_length=80)


class CategoriaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    activa: bool | None = None


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    nombre: str
    activa: bool


class PlantillaCreate(BaseModel):
    empresa_id: uuid.UUID | None = None
    marca_id: uuid.UUID | None = None
    sucursal_id: uuid.UUID | None = None
    categoria_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=120)
    descripcion: str | None = Field(default=None, max_length=500)
    momento: Momento
    orden: int = Field(default=1, ge=1)
    frecuencia: Frecuencia
    dia_semana: int | None = Field(default=None, ge=0, le=6)
    dia_mes: int | None = Field(default=None, ge=1, le=28)
    fecha_inicio: date
    requiere_foto: bool = False
    checklist: list[str] = Field(default_factory=list, min_length=1)
    asignado_a: uuid.UUID | None = None


class PlantillaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    descripcion: str | None = None
    orden: int | None = Field(default=None, ge=1)
    dia_semana: int | None = Field(default=None, ge=0, le=6)
    dia_mes: int | None = Field(default=None, ge=1, le=28)
    requiere_foto: bool | None = None
    checklist: list[str] | None = None
    asignado_a: uuid.UUID | None = None
    activa: bool | None = None


class PlantillaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    marca_id: uuid.UUID | None
    sucursal_id: uuid.UUID | None
    categoria_id: uuid.UUID
    nombre: str
    descripcion: str | None
    momento: str
    orden: int
    frecuencia: str
    dia_semana: int | None
    dia_mes: int | None
    fecha_inicio: date
    requiere_foto: bool
    checklist: list[str]
    asignado_a: uuid.UUID | None
    activa: bool


class TareaManualCreate(BaseModel):
    sucursal_id: uuid.UUID
    fecha: date
    momento: Momento
    categoria_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=120)
    orden: int = Field(default=1, ge=1)
    requiere_foto: bool = False
    checklist: list[str] = Field(default_factory=list)
    asignado_a: uuid.UUID | None = None


class AsignarBody(BaseModel):
    usuario_id: uuid.UUID


class MarcarItemBody(BaseModel):
    hecho: bool


class CompletarBody(BaseModel):
    observacion: str | None = Field(default=None, max_length=255)


class ChecklistItemOut(BaseModel):
    texto: str
    hecho: bool


class TareaInstanciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    plantilla_id: uuid.UUID | None
    sucursal_id: uuid.UUID
    fecha: date
    momento: str
    orden: int
    nombre: str
    categoria_id: uuid.UUID
    requiere_foto: bool
    checklist: list[ChecklistItemOut]
    asignado_a: uuid.UUID | None
    estado: str
    completada_at: datetime | None
    completada_por: uuid.UUID | None
    tiene_foto: bool = False
    foto_valida: bool | None
    observacion: str | None


class InformeDiarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sucursal_id: uuid.UUID
    fecha: date
    total: int
    completadas: int
    vencidas: int
    fotos_invalidas: int
    generado_at: datetime
