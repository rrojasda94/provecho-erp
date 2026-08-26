"""DTOs (pydantic) de entrada/salida del módulo users."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.shared.models.decision_gerencial import RESULTADOS, TIPOS
from src.shared.parametros import MODULOS
from src.shared.ubicacion import UbicacionMixin


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


class VerificarPinIn(BaseModel):
    """Desbloqueo de pantalla: solo el PIN. El usuario sale del token —
    pedirlo en el cuerpo dejaría verificar el PIN de cualquier otro."""

    pin: str


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
    # El PIN vigente lo puso otra persona. Viaja acá porque `/users/me` es
    # de lo poco que la cuenta puede pedir en ese estado, y el shell tiene
    # que saber que hay que mandarla a cambiarlo.
    debe_cambiar_pin: bool = False
    # El frontend las escribe como atributos de `<html>` durante el render en
    # servidor. Van en `/users/me` y no en un endpoint propio para que no haya
    # un instante en el que la pantalla ya se dibujó con la paleta equivocada.
    preferencia_paleta: str
    preferencia_tamano_fuente: str
    preferencia_tema: str


class PreferenciasIn(BaseModel):
    """Preferencias de presentación del usuario autenticado.

    Todas opcionales: la barra superior cambia una sola a la vez y mandar las
    otras dos obligaría al cliente a conocer el estado completo para tocar un
    campo.
    """

    paleta: Literal["estandar", "alto_contraste"] | None = None
    tamano_fuente: Literal["estandar", "grande", "muy_grande", "maximo"] | None = None
    tema: Literal["claro", "oscuro"] | None = None


# --- Persona (party model) ---
class PersonaCreate(UbicacionMixin):
    nombres: str = Field(max_length=100)
    apellidos: str = Field(max_length=100)
    tipo_documento: str
    numero_documento: str = Field(max_length=20)
    fecha_nacimiento: date | None = None
    domicilio: str | None = None
    telefono: str | None = None
    email: str | None = None


class PersonaUpdate(UbicacionMixin):
    version: int
    nombres: str | None = None
    apellidos: str | None = None
    tipo_documento: str | None = None
    numero_documento: str | None = None
    fecha_nacimiento: date | None = None
    domicilio: str | None = None
    telefono: str | None = None
    email: str | None = None


class PersonaOut(UbicacionMixin):
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


class NotificacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tipo: str
    nivel: str
    titulo: str
    cuerpo: str | None
    referencia_tipo: str | None
    referencia_id: uuid.UUID | None
    sucursal_id: uuid.UUID | None
    leida_at: datetime | None
    created_at: datetime


class AlmacenOut(UbicacionMixin):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    sucursal_id: uuid.UUID | None
    nombre: str
    tipo: str
    direccion: str | None
    almacen_abastecedor_id: uuid.UUID | None = None
    # A quién se le pide cuando el principal no está disponible
    # (RN-INV-022). Distinto del principal y de la misma empresa.
    almacen_abastecedor_respaldo_id: uuid.UUID | None = None
    # Siempre `False` salvo en el listado con `incluir_baja`, que es el único
    # que devuelve almacenes dados de baja. Se expone el hecho y no el
    # `deleted_at`: la fecha exacta de la baja no la usa ninguna pantalla.
    de_baja: bool = False


class MarcaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    grupo_id: uuid.UUID
    nombre: str
    tipo: str


class SucursalOut(UbicacionMixin):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    marca_id: uuid.UUID
    nombre: str
    estado: str
    direccion: str | None = None
    tenencia: str | None = None


# --- Organización (CRUD, permiso `organizacion.gestionar`) ---
# En todos los `Update`: un campo ausente o `null` = "no tocar". No hay
# forma de vaciar un opcional desde el PATCH; el día que haga falta, será
# un `Field` con centinela y no un `None` ambiguo.
class GrupoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)


class GrupoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)


class GrupoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str


TipoEmpresa = Literal[
    "operativa", "logistica", "servicios", "asesoria", "transporte"
]
ZonaTributaria = Literal["amazonia_ley27037", "general"]


class EmpresaCreate(UbicacionMixin):
    grupo_id: uuid.UUID
    razon_social: str = Field(min_length=1, max_length=255)
    # 11 dígitos: el RUC peruano no admite otra forma, y un RUC mal formado
    # llega hasta la factura electrónica antes de que alguien lo note.
    ruc: str = Field(pattern=r"^\d{11}$")
    domicilio_fiscal: str = Field(min_length=1, max_length=255)
    tipo: TipoEmpresa
    zona_tributaria: ZonaTributaria = "general"
    contacto: str | None = Field(default=None, max_length=255)
    config_fiscal: dict | None = None


class EmpresaUpdate(UbicacionMixin):
    razon_social: str | None = Field(default=None, min_length=1, max_length=255)
    ruc: str | None = Field(default=None, pattern=r"^\d{11}$")
    domicilio_fiscal: str | None = Field(default=None, min_length=1, max_length=255)
    tipo: TipoEmpresa | None = None
    zona_tributaria: ZonaTributaria | None = None
    contacto: str | None = Field(default=None, max_length=255)
    config_fiscal: dict | None = None


class EmpresaOut(UbicacionMixin):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    grupo_id: uuid.UUID
    razon_social: str
    ruc: str
    domicilio_fiscal: str
    contacto: str | None
    tipo: str
    zona_tributaria: str
    config_fiscal: dict | None


class MarcaCreate(BaseModel):
    # Opcional: sale del grupo de la empresa del tenant. Solo el
    # superusuario sin empresa asignada necesita indicarlo.
    grupo_id: uuid.UUID | None = None
    nombre: str = Field(min_length=1, max_length=100)
    tipo: str = Field(min_length=1, max_length=50)
    skins: dict | None = None


class MarcaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    tipo: str | None = Field(default=None, min_length=1, max_length=50)
    skins: dict | None = None


class LicenciaMarcaIn(BaseModel):
    marca_id: uuid.UUID


class LicenciaMarcaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    marca_id: uuid.UUID


TenenciaSucursal = Literal["propia", "alquilada", "del_grupo"]
EstadoSucursal = Literal["activa", "inactiva"]


class SucursalCreate(UbicacionMixin):
    marca_id: uuid.UUID
    # Igual que el resto del ERP: sale del tenant (ADR-004); informarla
    # ajena es 403.
    empresa_id: uuid.UUID | None = None
    nombre: str = Field(min_length=1, max_length=100)
    direccion: str = Field(min_length=1, max_length=255)
    tenencia: TenenciaSucursal
    estado: EstadoSucursal = "activa"
    horario_atencion: dict | None = None


class SucursalUpdate(UbicacionMixin):
    """Cerrar un local es `estado="inactiva"`; no hay DELETE de sucursal —
    sigue siendo el ancla de sus ventas, cajas y trabajadores."""

    marca_id: uuid.UUID | None = None
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    direccion: str | None = Field(default=None, min_length=1, max_length=255)
    tenencia: TenenciaSucursal | None = None
    estado: EstadoSucursal | None = None
    horario_atencion: dict | None = None


class AlmacenCreate(UbicacionMixin):
    empresa_id: uuid.UUID | None = None
    sucursal_id: uuid.UUID | None = None
    nombre: str = Field(min_length=1, max_length=100)
    # Enum extensible por diseño (data-model §1): `str`, no `Literal`.
    tipo: str = Field(min_length=1, max_length=30)
    direccion: str | None = Field(default=None, max_length=255)
    almacen_abastecedor_id: uuid.UUID | None = None
    # A quién se le pide cuando el principal no está disponible
    # (RN-INV-022). Distinto del principal y de la misma empresa.
    almacen_abastecedor_respaldo_id: uuid.UUID | None = None


class AlmacenUpdate(UbicacionMixin):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    tipo: str | None = Field(default=None, min_length=1, max_length=30)
    direccion: str | None = Field(default=None, max_length=255)
    sucursal_id: uuid.UUID | None = None
    almacen_abastecedor_id: uuid.UUID | None = None
    # A quién se le pide cuando el principal no está disponible
    # (RN-INV-022). Distinto del principal y de la misma empresa.
    almacen_abastecedor_respaldo_id: uuid.UUID | None = None


# --- Tokens de API de agentes (`tipo=agente_ia`) ---
class TokenAgenteCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    # NULL = sin vencimiento: una integración que corre sola no puede
    # quedarse tirada porque venció un token un domingo.
    dias_validez: int | None = Field(default=None, ge=1, le=3650)


class TokenAgenteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    usuario_id: uuid.UUID
    nombre: str
    prefijo: str
    expira_en: datetime | None
    revocado: bool
    ultimo_uso_en: datetime | None
    created_at: datetime


class TokenAgenteCreado(TokenAgenteOut):
    """El único momento en que el token en claro existe fuera de quien lo
    usa: después solo queda su SHA-256, y perderlo obliga a emitir otro."""

    token: str


class AnonimizarPersonaIn(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)


# --- Usuarios (admin) ---
class UsuarioCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    pin: str
    # `Literal` y no `str`: la columna es un Enum de dos valores, así que un
    # tipo inventado no llegaba a ser un 422 sino un 500 de SQLAlchemy al
    # hacer flush — el error salía del ORM, sin decir qué campo lo causó.
    tipo: Literal["humano", "agente_ia"] = "humano"
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


class PinPropioChange(BaseModel):
    """Cambio del PIN propio. Pide el actual aunque haya sesión válida: una
    pantalla que quedó abierta no debería alcanzar para quedarse la cuenta."""

    pin_actual: str
    pin_nuevo: str


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


