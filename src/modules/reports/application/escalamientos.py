"""Elevar un reporte por la cadena supervisor → comercial → gerencia.

El reporte informa; el escalamiento es lo que se hace con la información
cuando quien la recibe no puede resolverla (RN-CTP-004, ADR-036).

**Cada mutación publica su emisión al bus** y el listener genérico de
`application/listeners.py` la convierte en un reporte con sus entregas: quien
tiene que enterarse de que algo se elevó se entera por el mismo camino que
todo lo demás, sin un canal paralelo. No hay recursión — emitir un reporte no
abre un escalamiento.

**Cada mutación deja su fila en `audit_log`** (RN-REP-014), en la misma
transacción: elevar y resolver son actos de autoridad, igual que crear un área
o cambiar una regla.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.reports.application.errors import Conflicto, ReglaNegocio
from src.modules.reports.domain import escalamiento as reglas
from src.modules.reports.infrastructure.models import (
    ReporteEmitido,
    ReporteEscalamiento,
)
from src.modules.reports.infrastructure.repositories import EscalamientoRepo
from src.shared import auditoria


def _ahora() -> datetime:
    return datetime.now(UTC)


def _accion(nivel: str, usuario_id: uuid.UUID, accion: str, descripcion: str) -> dict:
    return {
        "nivel": nivel,
        "usuario_id": str(usuario_id),
        "accion": accion,
        "descripcion": descripcion,
        "ts": _ahora().isoformat(),
    }


def _agregar_accion(fila: ReporteEscalamiento, entrada: dict) -> None:
    """Append-only (RN-REP-012). Lista nueva y no `.append()`: SQLAlchemy no
    detecta la mutación in-place de un JSON y el historial se perdería en el
    commit sin que nadie se entere."""
    fila.acciones = [*(fila.acciones or []), entrada]


def _payload(fila: ReporteEscalamiento, reporte: ReporteEmitido, **extra) -> dict:
    return {
        "escalamiento_id": str(fila.id),
        "empresa_id": str(fila.empresa_id),
        "sucursal_id": str(fila.sucursal_id) if fila.sucursal_id else None,
        "reporte_emitido_id": str(reporte.id),
        "origen": fila.origen,
        "motivo": fila.motivo,
        "nivel_actual": fila.nivel_actual,
        "descripcion": fila.descripcion,
        "estado": fila.estado,
        **extra,
    }


def abrir(
    session: Session,
    reporte: ReporteEmitido,
    *,
    motivo: str,
    descripcion: str,
    reportado_por: uuid.UUID,
    evidencia_id: uuid.UUID | None = None,
    ip: str | None = None,
) -> ReporteEscalamiento:
    if motivo not in reglas.MOTIVOS:
        raise ReglaNegocio(f"motivo de escalamiento inválido: {motivo}")
    if reporte.empresa_id is None:
        # RN-REP-011. Un hecho que no se pudo atribuir a una empresa no tiene
        # área a la que elevarse ni permiso de módulo que lo cubra.
        raise ReglaNegocio(
            "un reporte que no se pudo atribuir a una empresa no se escala"
        )
    if reglas.exige_evidencia(motivo, (reporte.datos or {}).get("resultado")):
        if evidencia_id is None:
            raise ReglaNegocio(
                "una no conformidad que terminó en desecho exige evidencia "
                "(RN-PRD-015)"
            )
    repo = EscalamientoRepo(session)
    if repo.abierto_de(reporte.id) is not None:
        raise Conflicto("ese reporte ya tiene un escalamiento abierto")

    fila = repo.add(
        ReporteEscalamiento(
            empresa_id=reporte.empresa_id,
            sucursal_id=reporte.sucursal_id,
            reporte_emitido_id=reporte.id,
            origen=reglas.origen_de(
                reporte.referencia_tipo, reporte.sucursal_id, reporte.codigo_emision
            ),
            motivo=motivo,
            descripcion=descripcion,
            reportado_por_id=reportado_por,
            evidencia_id=evidencia_id,
            nivel_actual="supervisor",
            estado="abierto",
            acciones=[_accion("supervisor", reportado_por, "abrir", descripcion)],
        )
    )
    auditoria.registrar(
        session,
        usuario_id=reportado_por,
        entidad="reporte_escalamiento",
        entidad_id=fila.id,
        accion="abrir",
        datos_despues={"motivo": motivo, "nivel_actual": "supervisor"},
        empresa_id=fila.empresa_id,
        sucursal_id=fila.sucursal_id,
        ip=ip,
    )
    event_bus.publish(
        "reports.escalamiento_abierto",
        _payload(fila, reporte, reportado_por=str(reportado_por)),
        session=session,
    )
    return fila


def registrar_accion(
    session: Session,
    fila: ReporteEscalamiento,
    *,
    descripcion: str,
    usuario_id: uuid.UUID,
    ip: str | None = None,
) -> ReporteEscalamiento:
    """Lo que este nivel hizo, sin cambiar de nivel ni cerrar."""
    if not reglas.puede_accionar(fila.estado):
        raise Conflicto(f"el escalamiento está {fila.estado}; no admite acciones")
    _agregar_accion(fila, _accion(fila.nivel_actual, usuario_id, "accion", descripcion))
    auditoria.registrar(
        session,
        usuario_id=usuario_id,
        entidad="reporte_escalamiento",
        entidad_id=fila.id,
        accion="accion",
        datos_despues={"nivel": fila.nivel_actual, "descripcion": descripcion},
        empresa_id=fila.empresa_id,
        sucursal_id=fila.sucursal_id,
        ip=ip,
    )
    return fila


def elevar(
    session: Session,
    fila: ReporteEscalamiento,
    reporte: ReporteEmitido,
    *,
    descripcion: str,
    usuario_id: uuid.UUID,
    ip: str | None = None,
) -> ReporteEscalamiento:
    """Sube un escalón. Nunca dos: saltarse un nivel deja sin registro al que
    no intentó resolverlo, y ese registro es el insumo de la mejora continua.
    """
    if not reglas.puede_elevar(fila.estado, fila.nivel_actual):
        raise Conflicto(
            f"el escalamiento está {fila.estado} en nivel {fila.nivel_actual}; "
            "no se puede elevar más"
        )
    anterior = fila.nivel_actual
    fila.nivel_actual = reglas.siguiente_nivel(anterior)
    fila.estado = "escalado"
    _agregar_accion(fila, _accion(anterior, usuario_id, "elevar", descripcion))
    auditoria.registrar(
        session,
        usuario_id=usuario_id,
        entidad="reporte_escalamiento",
        entidad_id=fila.id,
        accion="elevar",
        datos_antes={"nivel_actual": anterior},
        datos_despues={"nivel_actual": fila.nivel_actual},
        empresa_id=fila.empresa_id,
        sucursal_id=fila.sucursal_id,
        ip=ip,
    )
    event_bus.publish(
        "reports.escalamiento_elevado",
        _payload(
            fila,
            reporte,
            nivel_anterior=anterior,
            elevado_por=str(usuario_id),
        ),
        session=session,
    )
    return fila


def resolver(
    session: Session,
    fila: ReporteEscalamiento,
    reporte: ReporteEmitido,
    *,
    descripcion: str,
    usuario_id: uuid.UUID,
    ip: str | None = None,
) -> ReporteEscalamiento:
    if not reglas.puede_accionar(fila.estado):
        raise Conflicto(f"el escalamiento está {fila.estado}; ya terminó")
    fila.estado = reglas.ESTADO_AL_RESOLVER[fila.nivel_actual]
    fila.cerrado_at = _ahora()
    _agregar_accion(
        fila, _accion(fila.nivel_actual, usuario_id, "resolver", descripcion)
    )
    auditoria.registrar(
        session,
        usuario_id=usuario_id,
        entidad="reporte_escalamiento",
        entidad_id=fila.id,
        accion="resolver",
        datos_despues={"estado": fila.estado, "nivel": fila.nivel_actual},
        empresa_id=fila.empresa_id,
        sucursal_id=fila.sucursal_id,
        ip=ip,
    )
    event_bus.publish(
        "reports.escalamiento_resuelto",
        _payload(fila, reporte, resuelto_por=str(usuario_id)),
        session=session,
    )
    return fila
