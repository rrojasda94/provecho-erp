"""CMS mínimo del sitio de marca: textos por marca y clave fija (ADR-101).

Los modelos `Hero`/`Nosotros`/... viven acá (no en `api/schemas.py`) porque
son la forma que este caso de uso valida al guardar, no una entrada de
FastAPI — guardar desde un script o un test tiene la misma garantía que
guardar desde el `PUT` del router.
"""

import uuid

import pydantic
from pydantic import BaseModel, Field

from src.modules.storefront.application.errors import ReglaNegocio
from src.modules.storefront.domain.rules import CLAVES_CONTENIDO
from src.modules.storefront.infrastructure.models import StorefrontContenido
from src.modules.storefront.infrastructure.repositories import ContenidoRepo


class Hero(BaseModel):
    titulo: str = Field(min_length=1, max_length=150)
    subtitulo: str | None = Field(default=None, max_length=300)
    cta_texto: str | None = Field(default=None, max_length=50)
    cta_url: str | None = Field(default=None, max_length=300)
    imagen_url: str | None = None


class HitoNosotros(BaseModel):
    anio: str = Field(min_length=1, max_length=20)
    texto: str = Field(min_length=1, max_length=300)


class Nosotros(BaseModel):
    titulo: str = Field(min_length=1, max_length=150)
    parrafos: list[str] = Field(default_factory=list)
    hitos: list[HitoNosotros] = Field(default_factory=list)


class Contacto(BaseModel):
    whatsapp: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=150)
    instagram: str | None = Field(default=None, max_length=150)
    facebook: str | None = Field(default=None, max_length=150)
    tiktok: str | None = Field(default=None, max_length=150)


class Trabaja(BaseModel):
    titulo: str = Field(min_length=1, max_length=150)
    cuerpo: str = Field(min_length=1, max_length=2000)


class Pie(BaseModel):
    texto: str = Field(min_length=1, max_length=500)


class Seo(BaseModel):
    titulo: str = Field(min_length=1, max_length=70)
    descripcion: str = Field(min_length=1, max_length=200)


#: `clave` → modelo que valida su `valor`. Único punto que hay que tocar al
#: agregar una clave nueva (junto con `domain.rules.CLAVES_CONTENIDO`).
MODELO_POR_CLAVE: dict[str, type[BaseModel]] = {
    "hero": Hero,
    "nosotros": Nosotros,
    "contacto": Contacto,
    "trabaja": Trabaja,
    "pie": Pie,
    "seo": Seo,
}
assert set(MODELO_POR_CLAVE) == set(CLAVES_CONTENIDO)


def listar(session, marca_id: uuid.UUID) -> list[StorefrontContenido]:
    return ContenidoRepo(session).listar(marca_id)


def guardar(
    session,
    *,
    marca_id: uuid.UUID,
    clave: str,
    valor: dict,
    actor_id: uuid.UUID | None,
) -> StorefrontContenido:
    if clave not in CLAVES_CONTENIDO:
        raise ReglaNegocio(f"clave de contenido desconocida: {clave}")
    modelo = MODELO_POR_CLAVE[clave]
    try:
        valor_validado = modelo.model_validate(valor).model_dump(mode="json")
    except pydantic.ValidationError as e:
        raise ReglaNegocio(f"contenido inválido para '{clave}': {e.errors()}") from e

    repo = ContenidoRepo(session)
    existente = repo.get(marca_id, clave)
    if existente is not None:
        existente.valor = valor_validado
        existente.updated_by = actor_id
        return existente
    return repo.add(
        StorefrontContenido(
            marca_id=marca_id,
            clave=clave,
            valor=valor_validado,
            updated_by=actor_id,
        )
    )


def contenido_publico(session, marca_id: uuid.UUID) -> dict[str, dict]:
    """`{clave: valor}` de todo lo que la marca tiene guardado — sin
    completar las claves ausentes: el sitio decide qué mostrar cuando falta
    una (ej. sin `hero` cargado, cae a un hero genérico en el propio front)."""
    return {c.clave: c.valor for c in ContenidoRepo(session).listar(marca_id)}
