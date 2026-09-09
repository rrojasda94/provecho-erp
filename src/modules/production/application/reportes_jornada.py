"""Reporte de producción de la jornada (RN-DOC-010): se genera solo con lo
que la cocina fue registrando durante el día — `generar_reporte_jornada`
consolida, `visar_reporte` es el único acto humano sobre el documento: se
visa, no se redacta.

`hora_cierre_jornada_de` sigue el mismo patrón que `application/tarifas.py`
y `application/reposicion.py` (`parametro_empresa` con semilla en
`settings`, ADR-014/068) — la usa el barrido de Celery (`application/
tasks.py`) para decidir cuándo, dentro del día, ya se puede cerrar la
jornada de cada almacén de producción.
"""

import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.events import event_bus
from src.modules.production.application.errors import Conflicto, NoEncontrado
from src.modules.production.domain import rules
from src.modules.production.infrastructure.models import ReporteProduccion
from src.modules.production.infrastructure.repositories import (
    OrdenProduccionRepo,
    ReporteProduccionRepo,
)
from src.modules.users.infrastructure.models import Almacen
from src.shared import auditoria, fechas, parametros

MODULO = "production"
CODIGO_HORA_CIERRE_JORNADA = "hora_cierre_jornada"


def _hora(valor: Any, clave: str, defecto: time) -> time:
    """Tolerante, mismo criterio que `tarifas._decimal`: un parámetro mal
    formado cobra la semilla, no tumba el barrido de cierre."""
    if not isinstance(valor, dict) or clave not in valor:
        return defecto
    try:
        return time.fromisoformat(str(valor[clave]))
    except (ValueError, TypeError):
        return defecto


def hora_cierre_jornada_de(session: Session, empresa_id: uuid.UUID | None) -> time:
    semilla = time.fromisoformat(settings.production_hora_cierre_jornada)
    if empresa_id is None:
        return semilla
    valor = parametros.valor_vigente(session, empresa_id, MODULO, CODIGO_HORA_CIERRE_JORNADA)
    return _hora(valor, "hora", semilla)


def q_reportes(
    session: Session,
    *,
    empresa_id: uuid.UUID | None = None,
    almacen_id: uuid.UUID | None = None,
    jornada: date | None = None,
):
    """La consulta sin ejecutar, para que el router la pagine (ADR-026)."""
    return ReporteProduccionRepo(session).q_list(
        empresa_id=empresa_id, almacen_id=almacen_id, jornada=jornada
    )


def _snapshot_ordenes(ordenes: list) -> list[dict]:
    return [
        {
            "orden_produccion_id": str(o.id),
            "articulo_id": str(o.articulo_id),
            "estado": o.estado,
            "cantidad_producida": str(o.cantidad_producida) if o.cantidad_producida else None,
            "costo_real_unitario": (
                str(o.costo_real_unitario) if o.costo_real_unitario else None
            ),
            "merma_cantidad": str(o.merma_cantidad) if o.merma_cantidad else None,
            "horas_hombre": str(o.horas_hombre) if o.horas_hombre else None,
        }
        for o in ordenes
    ]


def generar_reporte_jornada(
    session: Session,
    *,
    almacen_id: uuid.UUID,
    jornada: date | None = None,
    ip: str | None = None,
) -> ReporteProduccion:
    """Consolida las órdenes que cerraron control de calidad ese día en ese
    almacén. Recalcula el existente mientras no esté visado (una orden
    puede cerrar después de la primera corrida del día); una vez visado,
    queda congelado — RN-DOC-010 no admite reabrir lo ya aprobado."""
    almacen = session.get(Almacen, almacen_id)
    if almacen is None:
        raise NoEncontrado(f"almacén {almacen_id} no encontrado")
    jornada = jornada or fechas.hoy()

    repo = ReporteProduccionRepo(session)
    reporte = repo.get_por_clave(almacen_id, jornada)
    if reporte is not None and reporte.visado_at is not None:
        return reporte

    ordenes = OrdenProduccionRepo(session).completadas_en_jornada(almacen_id, jornada)
    merma_total = Decimal(0)
    desperdicio_total = Decimal(0)
    horas_hombre_total = Decimal(0)
    costo_total = Decimal(0)
    for orden in ordenes:
        if orden.estado == "no_conforme_desechado" and orden.merma_cantidad:
            merma_total += orden.merma_cantidad
        for item in OrdenProduccionRepo(session).consumos(orden.id):
            desperdicio_total += item.peso_desperdicio_real
        horas_hombre_total += orden.horas_hombre or Decimal(0)
        costo_total += (orden.costo_insumos or Decimal(0)) + (orden.costo_mano_obra or Decimal(0))

    if reporte is None:
        reporte = repo.add(ReporteProduccion(almacen_id=almacen_id, jornada=jornada))
    reporte.ordenes = _snapshot_ordenes(ordenes)
    reporte.merma_total = merma_total
    reporte.desperdicio_total = desperdicio_total
    reporte.horas_hombre_total = horas_hombre_total
    reporte.costo_total = costo_total
    reporte.generado_at = datetime.now(UTC)
    session.flush()

    auditoria.registrar(
        session,
        usuario_id=None,
        entidad="reporte_produccion",
        accion="generar",
        entidad_id=reporte.id,
        datos_despues={
            "almacen_id": str(almacen_id), "jornada": jornada.isoformat(),
            "ordenes": len(ordenes),
        },
        empresa_id=almacen.empresa_id,
        ip=ip,
    )
    event_bus.publish(
        "production.reporte_produccion_generado",
        {
            "reporte_produccion_id": str(reporte.id),
            "almacen_id": str(almacen_id),
            "jornada": jornada.isoformat(),
            "merma_total": str(merma_total),
            "desperdicio_total": str(desperdicio_total),
        },
        session=session,
    )
    return reporte


def visar_reporte(
    session: Session,
    reporte_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    observaciones: str | None = None,
    ip: str | None = None,
) -> ReporteProduccion:
    """El único acto humano sobre el documento (RN-DOC-010): visa lo que la
    jornada ya generó, no redacta contenido nuevo."""
    reporte = ReporteProduccionRepo(session).get(reporte_id)
    if reporte is None:
        raise NoEncontrado("reporte de producción no encontrado")
    if not rules.puede_visar_reporte(reporte.visado_at):
        raise Conflicto("el reporte ya está visado")

    reporte.visado_por = actor_id
    reporte.visado_at = datetime.now(UTC)
    if observaciones:
        reporte.observaciones = observaciones

    almacen = session.get(Almacen, reporte.almacen_id)
    auditoria.registrar(
        session,
        usuario_id=actor_id,
        entidad="reporte_produccion",
        accion="visar",
        entidad_id=reporte.id,
        datos_despues={"visado_por": str(actor_id)},
        empresa_id=almacen.empresa_id if almacen else None,
        ip=ip,
    )
    return reporte
