"""DTOs (pydantic) de entrada/salida del módulo users."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.shared.models.decision_gerencial import RESULTADOS, TIPOS
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


class AutorizacionIn(BaseModel):
    """El supervisor se identifica en el terminal del cajero para autorizar
    UNA acción (RN-AUD-005). No abre sesión: no sirve para llamar a
    cualquier endpoint ni se refresca."""

    username: str
    pin: str
    permiso: str


class AutorizacionOut(BaseModel):
    autorizacion: str
    autorizado_por: uuid.UUID
    expira_en_minutos: int


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


class PersonaBusquedaOut(BaseModel):
    """Para el selector de "elegir persona existente" de otro módulo
    (trabajador, proveedor natural) — nunca domicilio/teléfono/email/fecha
    de nacimiento. Mismo principio de minimización que `sales.cliente`: el
    lookup no es la ficha completa."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombres: str
    apellidos: str
    numero_documento: str | None


class AlmacenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    sucursal_id: uuid.UUID | None
    nombre: str
    tipo: str
    direccion: str | None


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


class DivisaCreate(BaseModel):
    codigo: str = Field(min_length=3, max_length=3)  # ISO 4217: PEN, USD
    nombre: str = Field(min_length=1, max_length=50)
    simbolo: str = Field(min_length=1, max_length=5)
    decimales: int = Field(ge=0, le=6, default=2)


class DivisaUpdate(BaseModel):
    nombre: str | None = None
    simbolo: str | None = None
    decimales: int | None = Field(default=None, ge=0, le=6)
    activa: bool | None = None


class DivisaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    codigo: str
    nombre: str
    simbolo: str
    decimales: int
    activa: bool


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


# --- Acta de decisión gerencial (RN-GER-002) ---
class DecisionGerencialCreate(BaseModel):
    """`decidido_por_id` NO viaja en el cuerpo: sale del token de quien
    ejerce el permiso. Un id suelto en el request permitiría atribuirle la
    decisión a otro gerente (mismo criterio que el descuento, RN-AUD-005)."""

    tipo: Literal[TIPOS]
    # Opcional: sale del tenant (ADR-004). Solo el superusuario sin empresa
    # asignada necesita indicarla; para el resto, informarla ajena es 403.
    empresa_id: uuid.UUID | None = None
    # Polimórfico sin FK: la tabla a la que apunta (`orden_compra`,
    # `campana`, `trabajador`...). Ver `shared/models/decision_gerencial.py`.
    referencia_tipo: str = Field(min_length=1, max_length=50)
    referencia_id: uuid.UUID
    sustento: str = Field(min_length=1)
    resultado: Literal[RESULTADOS]
    fecha: date
    condiciones: str | None = None
    ejecuta_area: Literal[MODULOS] | None = None
    archivo_id: uuid.UUID | None = None


class DecisionGerencialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    tipo: str
    referencia_tipo: str
    referencia_id: uuid.UUID
    decidido_por_id: uuid.UUID
    sustento: str
    resultado: str
    condiciones: str | None
    ejecuta_area: str | None
    fecha: date
    archivo_id: uuid.UUID | None


