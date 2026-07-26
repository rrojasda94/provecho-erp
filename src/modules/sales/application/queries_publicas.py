"""Contrato público de lectura de `sales` para otros módulos.

Único punto de entrada para que otro módulo (hoy: análisis vía API; a futuro:
`marketing` cuando exista como módulo) lea datos de clientes. Nunca importar
`sales.domain`/`sales.infrastructure` directamente desde otro módulo — solo
las funciones de este archivo, que devuelven DTOs (dicts), nunca el ORM.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.sales.infrastructure.models import Cliente
from src.modules.users.infrastructure.models import Persona


def listar_clientes_para_analisis(
    session: Session,
    grupo_id: uuid.UUID,
    *,
    tipo: str | None = None,
    limit: int = 200,
) -> list[dict]:
    stmt = (
        select(Cliente, Persona)
        .outerjoin(Persona, Persona.id == Cliente.persona_id)
        .where(Cliente.grupo_id == grupo_id, Cliente.deleted_at.is_(None))
        .limit(limit)
    )
    if tipo is not None:
        stmt = stmt.where(Cliente.tipo == tipo)

    resultado = []
    for cliente, persona in session.execute(stmt):
        nombre = (
            f"{persona.nombres} {persona.apellidos}"
            if persona is not None
            else cliente.razon_social
        )
        resultado.append(
            {
                "id": cliente.id,
                "tipo": cliente.tipo,
                "nombre": nombre,
                "contacto": cliente.contacto,
            }
        )
    return resultado
