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
from src.modules.users.infrastructure.models import Persona, Usuario


def nombres_por_usuario(
    session: Session, usuario_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, dict]:
    """`usuario_id` → nombre y cargo del trabajador, para etiquetar reportes
    de otros módulos (ej. ranking de venta por quien atendió).

    Un `usuario_id` sin trabajador asociado no aparece en el resultado: hay
    usuarios que no son personal (la cuenta de servicio del hub, el
    `agente_ia`). Quien llama decide cómo mostrarlos — inventar un nombre
    acá sería peor.

    La cuenta se resuelve por persona (ADR-070), y una persona recontratada
    puede tener dos filas `trabajador` compartiendo la misma cuenta. Entre
    esas, gana la que no está cesada, y si hay empate la de ingreso más
    reciente — sin este orden, el ranking podía etiquetar a alguien con su
    cargo viejo.
    """
    if not usuario_ids:
        return {}
    filas = session.execute(
        select(Usuario.id, Persona.nombres, Persona.apellidos, Trabajador.cargo)
        .join(Persona, Persona.id == Trabajador.persona_id)
        .join(Usuario, Usuario.persona_id == Trabajador.persona_id)
        .where(
            Usuario.id.in_(list(usuario_ids)),
            Usuario.deleted_at.is_(None),
            Trabajador.deleted_at.is_(None),
        )
        .order_by(
            (Trabajador.estado == "cesado").asc(),
            Trabajador.fecha_ingreso.desc(),
        )
    )
    resultado: dict[uuid.UUID, dict] = {}
    for usuario_id, nombres, apellidos, cargo in filas:
        # Primero gana: ya vienen ordenadas activo-primero / más reciente.
        resultado.setdefault(
            usuario_id, {"nombre": f"{nombres} {apellidos}".strip(), "cargo": cargo}
        )
    return resultado


def trabajador_resumen(session: Session, trabajador_id: uuid.UUID) -> dict | None:
    """Lo mínimo para que otro módulo valide a un trabajador como sujeto de
    algo suyo — hoy lo usa `assets` para el responsable de un activo y el
    sujeto de un documento con vencimiento (carné de sanidad, licencia de
    conducir). `None` si no existe o está borrado: quien llama decide si eso
    es un 404 o un dato opcional ausente.
    """
    fila = session.execute(
        select(Trabajador.id, Trabajador.empresa_id, Trabajador.sucursal_id,
               Trabajador.estado, Persona.nombres, Persona.apellidos)
        .join(Persona, Persona.id == Trabajador.persona_id)
        .where(Trabajador.id == trabajador_id, Trabajador.deleted_at.is_(None))
    ).first()
    if fila is None:
        return None
    trabajador_id, empresa_id, sucursal_id, estado, nombres, apellidos = fila
    return {
        "id": trabajador_id,
        "empresa_id": empresa_id,
        "sucursal_id": sucursal_id,
        "nombre": f"{nombres} {apellidos}".strip(),
        "estado": estado,
    }
