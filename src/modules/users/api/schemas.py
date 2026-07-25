"""DTOs (pydantic) de entrada/salida del módulo users."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


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
