"""Categorías de tarea de supervisión: CRUD simple, sin catálogo cerrado."""

import uuid

from sqlalchemy.orm import Session

from src.modules.supervision.application.errors import NoEncontrado
from src.modules.supervision.infrastructure.models import CategoriaTarea
from src.modules.supervision.infrastructure.repositories import CategoriaTareaRepo


def crear_categoria(session: Session, *, empresa_id: uuid.UUID, nombre: str) -> CategoriaTarea:
    categoria = CategoriaTareaRepo(session).add(
        CategoriaTarea(empresa_id=empresa_id, nombre=nombre)
    )
    return categoria


def q_categorias(session: Session, empresa_id: uuid.UUID | None = None):
    return CategoriaTareaRepo(session).q_list(empresa_id)


def editar_categoria(
    session: Session,
    categoria_id: uuid.UUID,
    *,
    nombre: str | None = None,
    activa: bool | None = None,
) -> CategoriaTarea:
    categoria = CategoriaTareaRepo(session).get(categoria_id)
    if categoria is None:
        raise NoEncontrado("categoría no encontrada")
    if nombre is not None:
        categoria.nombre = nombre
    if activa is not None:
        categoria.activa = activa
    session.flush()
    return categoria
