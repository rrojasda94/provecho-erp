"""Derechos ARCO sobre `persona` (Ley 29733, ADR-011).

Acceso y rectificación ya existen (`GET`/`PATCH /personas/{id}` en
`admin.py`). Este módulo cubre cancelación: **anonimización irreversible**,
no `DELETE` — `persona` la referencian `trabajador`/`cliente`/`usuario`, un
borrado físico rompería esas FK o dejaría planillas/comprobantes sin
sustento legal (retención tributaria/laboral).

Quien opera debe verificar, ANTES de llamar a esto, que no exista una
obligación de retención vigente en otro módulo (trabajador activo,
litigio, comprobante bajo retención tributaria) — no se valida acá:
`users` no importa el dominio de `rrhh`/`sales` (CLAUDE.md, ninguna
excepción para este caso), y muchas obligaciones de retención no son
modelables en una columna de todos modos. Ver ADR-011 para el checklist.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.modules.users.application.errors import Conflicto, NoEncontrado
from src.modules.users.infrastructure.models import Persona
from src.modules.users.infrastructure.repositories import AuditLogRepo, PersonaRepo

MARCADOR_ANONIMO = "ANONIMIZADO"
# Campos que se sobrescriben. numero_documento es UNIQUE: no puede quedar
# en NULL ni repetirse entre personas ya ancoradas, así que se reemplaza
# por un valor derivado del propio id, no por un texto fijo.
CAMPOS_ANONIMIZADOS = (
    "nombres",
    "apellidos",
    "numero_documento",
    "fecha_nacimiento",
    "domicilio",
    "telefono",
    "email",
)


def _numero_documento_anonimo(persona_id: uuid.UUID) -> str:
    # "ANON" + 15 hex = 19 chars, dentro del límite de la columna (20).
    return f"ANON{persona_id.hex[:15]}"


def anonimizar_persona(
    session: Session,
    persona_id: uuid.UUID,
    *,
    motivo: str,
    solicitado_por: uuid.UUID | None,
) -> Persona:
    repo = PersonaRepo(session)
    persona = repo.get(persona_id)
    if persona is None:
        raise NoEncontrado("persona no encontrada")
    if persona.anonimizado_at is not None:
        raise Conflicto("la persona ya fue anonimizada")

    persona.nombres = MARCADOR_ANONIMO
    persona.apellidos = MARCADOR_ANONIMO
    persona.numero_documento = _numero_documento_anonimo(persona.id)
    persona.fecha_nacimiento = None
    persona.domicilio = None
    persona.telefono = None
    persona.email = None
    persona.anonimizado_at = datetime.now(UTC)
    persona.version += 1

    # `datos_antes` deliberadamente NO lleva el valor real: guardar el
    # nombre/documento borrados en el audit_log dejaría la PII accesible
    # ahí para siempre, vaciando de sentido la anonimización. Se registra
    # el QUÉ se borró (campos) y el motivo, nunca el valor.
    AuditLogRepo(session).registrar(
        usuario_id=solicitado_por,
        entidad="persona",
        entidad_id=persona.id,
        accion="anonimizar",
        datos_despues={"campos_anonimizados": list(CAMPOS_ANONIMIZADOS), "motivo": motivo},
    )
    session.flush()
    return persona
