"""Paginación de colecciones (ADR-026).

Un solo sobre para toda la API — `{items, total, page, page_size}` — y un
solo lugar donde se cuenta y se corta. El `total` va aparte de los ítems
porque sin él el cliente no puede dibujar "página 3 de 12" ni decidir si
muestra el botón de siguiente.

**No lo usan todos los listados**: solo los que crecen con la operación
(ventas, movimientos, personas). Un catálogo de configuración —roles,
divisas, unidades de medida— tiene decenas de filas por definición y
paginarlo solo agrega un sobre que el cliente tiene que desenvolver. El
criterio y su frontera están en ADR-026.

El corte se hace **en la base** (`LIMIT`/`OFFSET`): traer 10 000 filas para
quedarse con 50 tendría el mismo costo que no paginar, que es justo lo que
se quiere evitar.
"""

from dataclasses import dataclass

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

PAGE_SIZE_DEFECTO = 50
# Techo duro: sin él, `page_size=1000000` es una forma cómoda de tumbar la
# API con una sola petición autenticada.
PAGE_SIZE_MAXIMO = 200


@dataclass(frozen=True)
class Paginacion:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def paginacion(
    page: int = Query(1, ge=1, description="Página, empezando en 1"),
    page_size: int = Query(
        PAGE_SIZE_DEFECTO,
        ge=1,
        le=PAGE_SIZE_MAXIMO,
        description=f"Filas por página (máx. {PAGE_SIZE_MAXIMO})",
    ),
) -> Paginacion:
    """Dependencia de FastAPI: `p: Paginacion = Depends(paginacion)`."""
    return Paginacion(page=page, page_size=page_size)


class Pagina[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


def paginar(session: Session, consulta: Select, p: Paginacion) -> dict:
    """Cuenta el total y devuelve la página pedida.

    Son dos consultas a propósito: `COUNT(*)` sobre la misma consulta sin
    `LIMIT`, y la página. La alternativa de una sola (`COUNT(*) OVER ()`)
    ahorra un viaje pero obliga a que cada listado devuelva la columna extra
    y la saque antes de serializar.
    """
    total = session.scalar(
        select(func.count()).select_from(consulta.order_by(None).subquery())
    )
    items = list(session.scalars(consulta.limit(p.page_size).offset(p.offset)))
    return {
        "items": items,
        "total": total or 0,
        "page": p.page,
        "page_size": p.page_size,
    }
