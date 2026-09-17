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


class VarianteCartaPublicaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    precio: Decimal
    disponible: bool
    ingredientes: list[IngredienteResumenOut] = []


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
