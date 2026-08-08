"""Auditoría transversal: el único punto de escritura de `audit_log`.

Cualquier módulo llama `registrar(...)` sin importar nada de otro módulo
(ADR-031). Antes esto era `users.infrastructure.repositories.AuditLogRepo`,
lo que obligaba a `rrhh` —y a todo el que quisiera dejar rastro— a entrar
por los repositorios de `users`.

Qué se audita: los actos de autoridad y de plata (aprobar, anular,
autorizar, descontar, pagar, anonimizar), no cada `UPDATE`. Un rastro que
registra todo no se lee, y el que no se lee no controla nada.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import Select, false, or_, select
from sqlalchemy.orm import Session

from src.shared.models.audit_log import AuditLog

# Logger propio, separado de `provecho.app` para que un colector pueda
# rutearlo aparte (retención distinta, alertas distintas).
log_auditoria = logging.getLogger("provecho.auditoria")


def registrar(
    session: Session,
    *,
    entidad: str,
    accion: str,
    entidad_id: uuid.UUID | None = None,
    usuario_id: uuid.UUID | None = None,
    datos_antes: dict | None = None,
    datos_despues: dict | None = None,
    empresa_id: uuid.UUID | None = None,
    sucursal_id: uuid.UUID | None = None,
    ip: str | None = None,
) -> AuditLog:
    """Agrega la entrada a la sesión en curso (misma transacción que el
    cambio auditado: si el cambio se revierte, el rastro también — auditar
    algo que no pasó es peor que no auditarlo).

    `datos_antes`/`datos_despues` son JSON: valores ya serializados
    (`str(monto)`, `str(uuid)`), no objetos ORM.
    """
    entry = AuditLog(
        usuario_id=usuario_id,
        entidad=entidad,
        entidad_id=entidad_id,
        accion=accion,
        datos_antes=datos_antes,
        datos_despues=datos_despues,
        empresa_id=empresa_id,
        sucursal_id=sucursal_id,
        ip=ip,
    )
    session.add(entry)
    # Además de la fila, una línea en el log estructurado. No es duplicar
    # por gusto: la tabla es el rastro legal (consultable, con su propia
    # retención) y el log es lo que un colector externo puede vigilar en
    # vivo — si alguien borrara la fila, la línea ya salió del proceso.
    # Solo metadatos: `datos_antes`/`datos_despues` pueden traer PII
    # (Ley 29733) y ese detalle se queda en la tabla.
    log_auditoria.info(
        "auditoria",
        extra={
            "accion": accion,
            "entidad": entidad,
            "entidad_id": str(entidad_id or ""),
            "usuario_id": str(usuario_id or ""),
            "ip": ip,
        },
    )
    return entry


def q_listar(
    *,
    empresa_id: uuid.UUID | None = None,
    sucursal_ids: frozenset[uuid.UUID] | None = None,
    entidad: str | None = None,
    entidad_id: uuid.UUID | None = None,
    usuario_id: uuid.UUID | None = None,
    accion: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
) -> Select:
    """La consulta sin ejecutar, para que el router la pagine (ADR-026).

    El alcance se pasa resuelto desde el `Tenant` (ADR-004). Los dos en
    `None` es "sin filtro de tenant" y solo vale para el superusuario:
    decidirlo es del router. Un usuario sin empresa y sin sucursales no ve
    nada — el caso ambiguo se resuelve cerrando, no abriendo.
    """
    stmt = select(AuditLog).order_by(AuditLog.ts.desc())

    if empresa_id is not None or sucursal_ids is not None:
        alcance = []
        if empresa_id is not None:
            alcance.append(AuditLog.empresa_id == empresa_id)
        if sucursal_ids:
            alcance.append(AuditLog.sucursal_id.in_(sucursal_ids))
        # Una fila sin empresa ni sucursal (login, alta de rol) queda fuera:
        # no hay forma de decir a qué tenant pertenece, y adivinarlo sería
        # filtrar el rastro de otra empresa.
        stmt = stmt.where(or_(*alcance) if alcance else false())

    if entidad is not None:
        stmt = stmt.where(AuditLog.entidad == entidad)
    if entidad_id is not None:
        stmt = stmt.where(AuditLog.entidad_id == entidad_id)
    if usuario_id is not None:
        stmt = stmt.where(AuditLog.usuario_id == usuario_id)
    if accion is not None:
        stmt = stmt.where(AuditLog.accion == accion)
    if desde is not None:
        stmt = stmt.where(AuditLog.ts >= desde)
    if hasta is not None:
        stmt = stmt.where(AuditLog.ts <= hasta)
    return stmt
