"""DTOs (pydantic) de entrada/salida del módulo users."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.shared.parametros import MODULOS


# --- Auth ---
class LoginIn(BaseModel):
    username: str
    pin: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class MeOut(BaseModel):
    id: uuid.UUID
    username: str
    tipo: str
    roles: list[str]
    sucursales: list[uuid.UUID]
    empresa_id: uuid.UUID | None
    permisos: list[str]


# --- Persona (party model) ---
class PersonaCreate(BaseModel):
    nombres: str = Field(max_length=100)
    apellidos: str = Field(max_length=100)
    tipo_documento: str
    numero_documento: str = Field(max_length=20)
    fecha_nacimiento: date | None = None
    domicilio: str | None = None
    telefono: str | None = None
    email: str | None = None


class PersonaUpdate(BaseModel):
    version: int
    nombres: str | None = None
    apellidos: str | None = None
    tipo_documento: str | None = None
    numero_documento: str | None = None
    fecha_nacimiento: date | None = None
    domicilio: str | None = None
    telefono: str | None = None
    email: str | None = None


class PersonaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombres: str
    apellidos: str
    tipo_documento: str
    numero_documento: str
    fecha_nacimiento: date | None
    domicilio: str | None
    telefono: str | None
    email: str | None
    version: int
    anonimizado_at: datetime | None


class AnonimizarPersonaIn(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)


# --- Usuarios (admin) ---
class UsuarioCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    pin: str
    tipo: str = "humano"
    persona_id: uuid.UUID | None = None
    nombre_display: str | None = None
    email: str | None = None


class UsuarioUpdate(BaseModel):
    nombre_display: str | None = None
    email: str | None = None
    activo: bool | None = None
    persona_id: uuid.UUID | None = None


class PinChange(BaseModel):
    pin: str


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str
    tipo: str
    persona_id: uuid.UUID | None
    nombre_display: str | None
    email: str | None
    activo: bool


# --- Roles / permisos (admin) ---
class RolCreate(BaseModel):
    nombre: str
    descripcion: str | None = None


class RolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    descripcion: str | None


class PermisoCreate(BaseModel):
    codigo: str
    descripcion: str | None = None
    restricciones: dict | None = None


class PermisoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    codigo: str
    descripcion: str | None
    restricciones: dict | None


class RolIdIn(BaseModel):
    rol_id: uuid.UUID


class PermisoIdIn(BaseModel):
    permiso_id: uuid.UUID


class SucursalIdIn(BaseModel):
    sucursal_id: uuid.UUID


# --- Parámetros operativos por empresa (ADR-014, RN-GER-008/009) ---
class ParametroPropuesta(BaseModel):
    empresa_id: uuid.UUID
    # `Literal` sobre el catálogo real: un módulo inventado no mapea a ningún
    # permiso `<modulo>.proponer_parametro` y debe morir en el borde (422).
    modulo: Literal[MODULOS]
    codigo: str = Field(max_length=50)
    valor: dict
    motivo: str | None = None


class ParametroAprobacion(BaseModel):
    # `valor` no nulo = Gerencia modifica el valor propuesto antes de aprobar.
    valor: dict | None = None


class ParametroRechazo(BaseModel):
    motivo_rechazo: str = Field(min_length=1, max_length=500)


class ParametroEmpresaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    modulo: str
    codigo: str
    valor: dict
    # Magnitud con su unidad tal como se le mostró a Gerencia ("S/ 2000.00").
    valor_display: str | None
    estado: str
    propuesto_por_id: uuid.UUID
    motivo: str | None
    resuelto_por_id: uuid.UUID | None
    resuelto_en: datetime | None
    motivo_rechazo: str | None


