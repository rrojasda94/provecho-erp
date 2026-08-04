"""Contrato público de lectura de `rrhh` para otros módulos.

Mismo criterio que `sales.application.queries_publicas`: único punto de
entrada para leer datos de `rrhh` desde afuera, devolviendo DTOs (dicts),
nunca el ORM. Nadie importa `rrhh.infrastructure` desde otro módulo.

Lo que se expone acá es deliberadamente lo **mínimo identificatorio**:
nombre y cargo para poder etiquetar un ranking. Remuneración, régimen
pensionario, contratos y sanciones no salen de `rrhh` por ningún contrato
— quien los necesite pasa por su API con `rrhh.leer`.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.rrhh.infrastructure.models import Trabajador
from src.modules.users.infrastructure.models import Persona


def nombres_por_usuario(
    session: Session, usuario_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, dict]:
    """`usuario_id` → nombre y cargo del trabajador, para etiquetar reportes
    de otros módulos (ej. ranking de venta por quien atendió).

    Un `usuario_id` sin trabajador asociado no aparece en el resultado: hay
    usuarios que no son personal (la cuenta de servicio del hub, el
    `agente_ia`). Quien llama decide cómo mostrarlos — inventar un nombre
    acá sería peor.
    """
    if not usuario_ids:
        return {}
    filas = session.execute(
        select(Trabajador.usuario_id, Persona.nombres, Persona.apellidos, Trabajador.cargo)
        .join(Persona, Persona.id == Trabajador.persona_id)
        .where(
            Trabajador.usuario_id.in_(list(usuario_ids)),
            Trabajador.deleted_at.is_(None),
        )
    )
    return {
        usuario_id: {"nombre": f"{nombres} {apellidos}".strip(), "cargo": cargo}
        for usuario_id, nombres, apellidos, cargo in filas
    }
