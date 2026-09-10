"""Casos de uso del plan de producción: cronograma fijo por línea/turno
(RN-PRD-007/012). `crear` (planificado) → agregar órdenes → `iniciar`
(reserva los insumos de todas sus órdenes) → `cerrar` (libera lo que no
se llegó a consumir).

La reserva de insumos vive en `inventory` (`application/reservas.py`,
`reserva_stock.tipo="produccion"` — un tipo que existía desde ADR-028 sin
ningún productor, ver `inventory/README.md`): se llama directo, no por
evento, porque `iniciar` necesita saber **antes de responder** si el
stock alcanza (`StockInsuficiente` interrumpe la transacción entera, sin
dejar reservas a medias — la sesión hace rollback sola ante cualquier
excepción, `core/error_handlers.py`). Cada reserva se referencia a la
`orden_produccion.id` que la necesita, no al plan: es el mismo criterio
que usa el resto del ERP (`solicitud_id`, `merma_id`) y es lo que permite
liberarla o consumirla por orden sin tocar las demás del mismo plan.
"""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from src.modules.inventory.application import queries_publicas as inv_queries
from src.modules.inventory.application import reservas as reservas_uc
from src.modules.production.application import ordenes as ordenes_uc
from src.modules.production.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.production.domain import rules
from src.modules.production.infrastructure.models import OrdenProduccion, PlanProduccion
from src.modules.production.infrastructure.repositories import (
    OrdenProduccionRepo,
    PlanProduccionRepo,
)
from src.modules.users.infrastructure.models import Almacen
from src.shared import auditoria


def q_planes(
    session: Session,
    *,
    empresa_id: uuid.UUID | None = None,
    almacen_id: uuid.UUID | None = None,
    fecha: date | None = None,
    estado: str | None = None,
):
    """La consulta sin ejecutar, para que el router la pagine (ADR-026)."""
    return PlanProduccionRepo(session).q_list(
        empresa_id=empresa_id, almacen_id=almacen_id, fecha=fecha, estado=estado
    )


def crear_plan(
    session: Session,
    *,
    almacen_id: uuid.UUID,
    fecha: date,
    turno: str,
    linea_produccion: str,
    creado_por: uuid.UUID | None,
    origen: str = "cronograma_fijo",
    ip: str | None = None,
) -> PlanProduccion:
    almacen = session.get(Almacen, almacen_id)
    if almacen is None:
        raise NoEncontrado(f"almacén {almacen_id} no encontrado")
    repo = PlanProduccionRepo(session)
    if repo.get_por_clave(almacen_id, fecha, turno, linea_produccion) is not None:
        raise Conflicto(
            f"ya hay un plan para '{linea_produccion}' en el turno '{turno}' de "
            f"{fecha} en ese almacén (RN-PRD-012)"
        )
    plan = repo.add(
        PlanProduccion(
            almacen_id=almacen_id,
            fecha=fecha,
            turno=turno,
            linea_produccion=linea_produccion,
            origen=origen,
            creado_por=creado_por,
        )
    )
    auditoria.registrar(
        session,
        usuario_id=creado_por,
        entidad="plan_produccion",
        accion="crear",
        entidad_id=plan.id,
        datos_despues={
            "almacen_id": str(almacen_id), "fecha": fecha.isoformat(),
            "turno": turno, "linea_produccion": linea_produccion,
        },
        empresa_id=almacen.empresa_id,
        ip=ip,
    )
    return plan


def agregar_orden(
    session: Session,
    plan_id: uuid.UUID,
    *,
    articulo_id: uuid.UUID,
    cantidad_planeada,
    creado_por: uuid.UUID | None,
    idempotency_key: str,
    ip: str | None = None,
) -> OrdenProduccion:
    plan = PlanProduccionRepo(session).get(plan_id)
    if plan is None:
        raise NoEncontrado("plan de producción no encontrado")
    if plan.estado != "planificado":
        raise Conflicto(
            f"el plan está {plan.estado}; ya no admite agregar órdenes nuevas"
        )
    orden = ordenes_uc.crear_orden_produccion(
        session,
        articulo_id=articulo_id,
        almacen_id=plan.almacen_id,
        cantidad_planeada=cantidad_planeada,
        creado_por=creado_por,
        idempotency_key=idempotency_key,
        origen="plan",
        ip=ip,
    )
    if orden.plan_produccion_id is None:
        orden.plan_produccion_id = plan.id
        session.flush()
    return orden


def iniciar_plan(
    session: Session, plan_id: uuid.UUID, *, actor_id: uuid.UUID | None, ip: str | None = None
) -> PlanProduccion:
    """Reserva los insumos de todas las órdenes del plan (RN-PRD-007): si
    algo no alcanza, `StockInsuficiente` interrumpe todo el `iniciar` —
    Gerencia se entera del faltante antes de comprometer la jornada, no
    después, a medio turno."""
    plan = PlanProduccionRepo(session).get(plan_id)
    if plan is None:
        raise NoEncontrado("plan de producción no encontrado")
    if not rules.puede_iniciar_plan(plan.estado):
        raise Conflicto(f"el plan está {plan.estado}; no admite iniciarse")
    ordenes_del_plan = OrdenProduccionRepo(session).de_plan(plan.id)
    if not ordenes_del_plan:
        raise ReglaNegocio("el plan no tiene ninguna orden que reservar")

    for orden in ordenes_del_plan:
        sugerido = inv_queries.consumo_sugerido_de_receta(
            session, orden.articulo_id, orden.cantidad_planeada
        )
        if sugerido is None:
            continue  # no debería pasar: crear_orden_produccion ya exige receta
        for linea in sugerido["items"]:
            sku_id = inv_queries.sku_de_articulo(session, linea["articulo_id"])
            if sku_id is None:
                continue  # sin SKU activo: no hay qué reservar, se verá al consumir
            reservas_uc.reservar(
                session,
                almacen_id=plan.almacen_id,
                sku_id=sku_id,
                cantidad=linea["cantidad_sugerida"],
                tipo="produccion",
                creado_por=actor_id,
                referencia_id=orden.id,
            )

    estado_previo = plan.estado
    plan.estado = "en_ejecucion"
    almacen = session.get(Almacen, plan.almacen_id)
    auditoria.registrar(
        session,
        usuario_id=actor_id,
        entidad="plan_produccion",
        accion="iniciar",
        entidad_id=plan.id,
        datos_antes={"estado": estado_previo},
        datos_despues={"estado": "en_ejecucion"},
        empresa_id=almacen.empresa_id if almacen else None,
        ip=ip,
    )
    return plan


def cerrar_plan(
    session: Session, plan_id: uuid.UUID, *, actor_id: uuid.UUID | None, ip: str | None = None
) -> PlanProduccion:
    """Libera lo que ninguna orden llegó a consumir (RN-PRD-011): el
    disponible vuelve solo, no queda esperando a que alguien note la
    reserva colgada."""
    plan = PlanProduccionRepo(session).get(plan_id)
    if plan is None:
        raise NoEncontrado("plan de producción no encontrado")
    if not rules.puede_cerrar_plan(plan.estado):
        raise Conflicto(f"el plan está {plan.estado}; no admite cerrarse")

    for orden in OrdenProduccionRepo(session).de_plan(plan.id):
        reservas_uc.liberar_por_referencia(session, orden.id, liberado_por=actor_id)

    estado_previo = plan.estado
    plan.estado = "cerrado"
    almacen = session.get(Almacen, plan.almacen_id)
    auditoria.registrar(
        session,
        usuario_id=actor_id,
        entidad="plan_produccion",
        accion="cerrar",
        entidad_id=plan.id,
        datos_antes={"estado": estado_previo},
        datos_despues={"estado": "cerrado"},
        empresa_id=almacen.empresa_id if almacen else None,
        ip=ip,
    )
    return plan
