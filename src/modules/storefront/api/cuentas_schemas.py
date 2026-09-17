"""Schemas de la cuenta de cliente del sitio (ADR-102)."""

import re
import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from src.shared.ubicacion import UbicacionMixin

# Formato, no entregabilidad: el resto del ERP tampoco valida email con una
# librería aparte (`persona.email` es `str | None` liso). Rechaza lo obvio
# ("sin arroba") sin pretender ser RFC 5322 completo.
_PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validar_email(v: str) -> str:
    v = v.strip().lower()
    if not _PATRON_EMAIL.match(v):
        raise ValueError("email inválido")
    return v


Email = Annotated[str, AfterValidator(_validar_email)]


class RegistroIn(UbicacionMixin):
    email: Email
    password: str = Field(min_length=8, max_length=255)
    nombres: str = Field(min_length=1, max_length=150)
    apellidos: str = Field(min_length=1, max_length=150)
    tipo_documento: str = Field(default="dni", max_length=10)
    numero_documento: str = Field(min_length=8, max_length=15)
    telefono: str = Field(min_length=6, max_length=20)
    fecha_nacimiento: date
    direccion: str | None = Field(default=None, max_length=255)


class LoginIn(BaseModel):
    email: Email
    password: str


class GoogleLoginIn(UbicacionMixin):
    id_token: str
    # Solo se usan si la cuenta es nueva (RN-WEB-005): Google confirma el
    # email, no el resto del perfil.
    nombres: str | None = Field(default=None, max_length=150)
    apellidos: str | None = Field(default=None, max_length=150)
    tipo_documento: str | None = Field(default=None, max_length=10)
    numero_documento: str | None = Field(default=None, max_length=15)
    telefono: str | None = Field(default=None, max_length=20)
    fecha_nacimiento: date | None = None
    direccion: str | None = Field(default=None, max_length=255)


class RefreshIn(BaseModel):
    refresh_token: str


class TokensOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class CuentaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    nombres: str
    apellidos: str
    tipo_documento: str | None
    numero_documento: str | None
    telefono: str | None
    fecha_nacimiento: date | None
    tiene_password: bool = False
    tiene_google: bool = False


class ActualizarPerfilIn(BaseModel):
    nombres: str | None = Field(default=None, min_length=1, max_length=150)
    apellidos: str | None = Field(default=None, min_length=1, max_length=150)
    telefono: str | None = Field(default=None, max_length=20)


class DireccionIn(UbicacionMixin):
    etiqueta: str | None = Field(default=None, max_length=50)
    direccion: str = Field(min_length=1, max_length=255)
    referencia: str | None = Field(default=None, max_length=255)
    predeterminada: bool = False


class DireccionUpdateIn(UbicacionMixin):
    etiqueta: str | None = Field(default=None, max_length=50)
    direccion: str | None = Field(default=None, max_length=255)
    referencia: str | None = Field(default=None, max_length=255)
    predeterminada: bool | None = None


class DireccionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    etiqueta: str | None
    direccion: str
    referencia: str | None
    predeterminada: bool
    ubicacion_lat: Decimal | None = None
    ubicacion_lng: Decimal | None = None


class FavoritoIn(BaseModel):
    producto_comercial_id: uuid.UUID


class UltimoPedidoItemOut(BaseModel):
    nombre: str
    cantidad: Decimal


class UltimoPedidoOut(BaseModel):
    id: uuid.UUID
    numero_orden: int
    fecha_orden: date
    estado: str
    total: Decimal
    canal: str
    modalidad: str
    items: list[UltimoPedidoItemOut]
