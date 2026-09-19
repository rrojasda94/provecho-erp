"""Schemas Pydantic de `storefront`: gestión (JWT) y públicos (sin JWT).

La forma de `valor` por clave del CMS (`Hero`, `Nosotros`, ...) vive en
`application/contenido.py`, no acá: `api → application` es la única
dirección permitida (`docs/engineering/module-guide.md`), y esos modelos
son los que valida el caso de uso al guardar, no una forma de entrada de
FastAPI.
"""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

ClaveContenido = Literal["hero", "nosotros", "contacto", "trabaja", "pie", "seo"]


# --- Gestión (JWT, `storefront.leer`/`storefront.editar`) ---
class ContenidoIn(BaseModel):
    valor: dict


class ContenidoOut(BaseModel):
    clave: ClaveContenido
    valor: dict
    updated_by: uuid.UUID | None = None
    updated_at: datetime


class PresignFotoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)


class PresignFotoOut(BaseModel):
    upload_url: str
    url_storage: str


class FotoRegistrarIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    tamano_bytes: int = Field(gt=0)
    url_storage: str = Field(min_length=1, max_length=500)


class FotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    mime_type: str
    url_storage: str
    created_at: datetime


EntidadFoto = Literal["producto", "ingrediente"]


# --- Atención al cliente (ERP: `/web/clientes`) ---
class ClienteWebOut(BaseModel):
    """Una cuenta del sitio vista por el personal: datos de contacto, nunca la
    clave ni su hash."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    nombres: str
    apellidos: str
    telefono: str | None = None
    numero_documento: str | None = None
    tiene_password: bool = False
    tiene_google: bool = False
    debe_cambiar_clave: bool = False
    created_at: datetime


class ClaveTemporalOut(BaseModel):
    """Se muestra una sola vez a quien atiende: no queda guardada en claro."""

    clave_temporal: str


# --- Horario estructurado (ver data-model.md) ---
class HorarioAtencion(RootModel[dict[str, list[tuple[str, str]]]]):
    """`{"lun": [["11:00","23:00"]], ...}`. No se valida a nivel de tipo si
    las claves son exactamente los 7 días esperados — `sucursal.py` acepta
    filas heredadas con otra forma (JSONB libre); esto solo tipa lo que el
    formulario del ERP escribe."""

    pass


# --- Públicos (sin JWT, RN-WEB-001..004) ---
class MarcaPublicaOut(BaseModel):
    nombre: str


class ContenidoPublicoOut(BaseModel):
    marca: MarcaPublicaOut
    contenido: dict[str, dict]


class IngredienteResumenOut(BaseModel):
    id: uuid.UUID
    nombre: str


class ExtraPublicoOut(BaseModel):
    """Un extra que se puede sumar a la línea. `precio` es por unidad del
    extra; `maximo` el tope por unidad del producto; si pertenece a un grupo,
    `grupo_minimo`/`grupo_maximo` dicen cuántos hay que elegir (un sabor
    obligatorio es un grupo con mínimo 1)."""

    id: uuid.UUID
    nombre: str
    precio: Decimal
    maximo: int | None = None
    grupo_id: uuid.UUID | None = None
    grupo_nombre: str | None = None
    grupo_minimo: int = 0
    grupo_maximo: int | None = None


class ValorAtributoPublicoOut(BaseModel):
    id: uuid.UUID
    nombre: str
    precio_extra: Decimal


class AtributoPublicoOut(BaseModel):
    """Algo que hay que elegir una vez (una mitad de la Mitad x Mitad)."""

    id: uuid.UUID
    nombre: str
    display: str | None = None
    valores: list[ValorAtributoPublicoOut] = []


class VarianteCartaPublicaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    precio: Decimal
    disponible: bool
    ingredientes: list[IngredienteResumenOut] = []
    # Solo en el detalle del producto (`/productos/{id}`), no en `/carta`.
    extras: list[ExtraPublicoOut] = []
    atributos: list[AtributoPublicoOut] = []
    exclusiones: list[tuple[uuid.UUID, uuid.UUID]] = []


class ProductoCartaPublicaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    descripcion: str | None = None
    categoria_id: uuid.UUID | None = None
    precio_desde: Decimal
    foto_url: str | None = None
    disponible: bool
    ingredientes: list[IngredienteResumenOut] = []
    variantes: list[VarianteCartaPublicaOut] = []
    # Las de un producto sin presentaciones (con presentaciones van en cada
    # una). Solo en el detalle.
    extras: list[ExtraPublicoOut] = []
    atributos: list[AtributoPublicoOut] = []
    exclusiones: list[tuple[uuid.UUID, uuid.UUID]] = []


class CategoriaCartaOut(BaseModel):
    id: uuid.UUID
    nombre: str


class CartaPublicaOut(BaseModel):
    categorias: list[CategoriaCartaOut] = []
    productos: list[ProductoCartaPublicaOut] = []


class ProductoPublicoDetalleOut(ProductoCartaPublicaOut):
    fotos: list[str] = []
    ingredientes_detalle: list["IngredientePublicoOut"] = []


class IngredientePublicoOut(BaseModel):
    id: uuid.UUID
    nombre: str
    descripcion: str | None = None
    foto_url: str | None = None


class SucursalPublicaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    direccion: str | None = None
    telefono: str | None = None
    horario_atencion: dict | None = None
    lat: Decimal | None = None
    lng: Decimal | None = None
    abierto_ahora: bool | None = None


class PromocionPublicaWebOut(BaseModel):
    id: uuid.UUID
    nombre: str
    tipo: str
    beneficio: dict | None = None
    desde: date | None = None
    hasta: date | None = None
    dias_semana: list[int] | None = None
    hora_desde: time | None = None
    hora_hasta: time | None = None


class ConvocatoriaPublicaWebOut(BaseModel):
    token: str
    puesto: str
    sucursal_nombre: str | None = None
    vacantes: int
    jornada_horas_semana: Decimal | None = None
    fecha_limite: date | None = None
    url_postular: str


ProductoPublicoDetalleOut.model_rebuild()
