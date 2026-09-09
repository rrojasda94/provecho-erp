"""Orden de mantenimiento: ejecución de un plan o adelanto por avería
(RN-MNT-002/003/004)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.assets.application import vehiculos as vehiculos_uc
from src.modules.assets.application.errors import NoEncontrado, ReglaNegocio
from src.modules.assets.domain import rules
from src.modules.assets.infrastructure.models import OrdenMantenimiento
from src.modules.assets.infrastructure.repositories import (
    ActivoRepo,
    OrdenMantenimientoRepo,
    PlanMantenimientoRepo,
    VehiculoRepo,
)
from src.shared import auditoria


def crear_orden(
    session: Session,
    *,
    activo_id: uuid.UUID,
    tipo: str,
    reportado_por: uuid.UUID,
    plan_id: uuid.UUID | None = None,
    motivo_adelanto: str | None = None,
    fecha_programada: date | None = None,
    proveedor_servicio_id: uuid.UUID | None = None,
    descripcion: str | None = None,
) -> OrdenMantenimiento:
    activo = ActivoRepo(session).get(activo_id)
    if activo is None:
        raise NoEncontrado("activo no encontrado")
    if tipo not in rules.TIPOS_ORDEN_MANTENIMIENTO:
        raise ReglaNegocio(f"tipo de orden inválido: {tipo}")
    if tipo == "adelantado" and motivo_adelanto is None:
        raise ReglaNegocio("una orden adelantada requiere motivo_adelanto (RN-MNT-003)")
    if plan_id is not None:
        plan = PlanMantenimientoRepo(session).get(plan_id)
        if plan is None or plan.activo_id != activo_id:
            raise NoEncontrado("plan de mantenimiento no encontrado para este activo")

    return OrdenMantenimientoRepo(session).add(
        OrdenMantenimiento(
            activo_id=activo_id,
            plan_id=plan_id,
            tipo=tipo,
            motivo_adelanto=motivo_adelanto,
            fecha_programada=fecha_programada,
            proveedor_servicio_id=proveedor_servicio_id,
            reportado_por=reportado_por,
            descripcion=descripcion,
        )
    )


def iniciar_orden(session: Session, orden: OrdenMantenimiento) -> OrdenMantenimiento:
    if not rules.puede_iniciar_orden(orden.estado):
        raise ReglaNegocio(f"la orden está {orden.estado}: no se puede iniciar")
    orden.estado = "en_curso"
    activo = ActivoRepo(session).get(orden.activo_id)
    if activo is not None and activo.estado == "operativo":
        activo.estado = "en_mantenimiento"
    return orden


def realizar_orden(
    session: Session,
    orden: OrdenMantenimiento,
    *,
    actor_id: uuid.UUID,
    fecha_realizada: date,
    km_al_realizar: int | None = None,
    resultado: str | None = None,
    costo: Decimal | None = None,
    comprobante_id: uuid.UUID | None = None,
) -> OrdenMantenimiento:
    if not rules.puede_realizar_orden(orden.estado):
        raise ReglaNegocio(f"la orden está {orden.estado}: no se puede realizar")

    estado_antes = orden.estado
    orden.estado = "realizada"
    orden.fecha_realizada = fecha_realizada
    orden.km_al_realizar = km_al_realizar
    orden.resultado = resultado
    orden.costo = costo
    orden.comprobante_id = comprobante_id

    activo = ActivoRepo(session).get(orden.activo_id)
    if activo is not None and activo.estado != "de_baja":
        activo.estado = "operativo"

    if activo is not None and activo.tipo == "vehiculo" and km_al_realizar is not None:
        vehiculo = VehiculoRepo(session).get(activo.id)
        if vehiculo is not None:
            vehiculos_uc.registrar_lectura(
                session,
                vehiculo,
                km=km_al_realizar,
                fecha=fecha_realizada,
                origen="mantenimiento",
                registrado_por=actor_id,
            )

    if orden.plan_id is not None:
        plan = PlanMantenimientoRepo(session).get(orden.plan_id)
        if plan is not None:
            plan.ultima_fecha = fecha_realizada
            if km_al_realizar is not None:
                plan.ultimo_km = km_al_realizar
            # El plan vuelve a estar al día: los avisos publicados para el
            # ciclo que se acaba de cerrar ya no describen la realidad.
            plan.aviso_proximo_en = None
            plan.aviso_vencido_en = None

    auditoria.registrar(
        session,
        entidad="orden_mantenimiento",
        accion="realizar",
        entidad_id=orden.id,
        usuario_id=actor_id,
        datos_antes={"estado": estado_antes},
        datos_despues={"estado": "realizada", "costo": str(costo) if costo else None},
        empresa_id=activo.empresa_id if activo else None,
        sucursal_id=activo.sucursal_id if activo else None,
    )
    return orden


def cancelar_orden(
    session: Session, orden: OrdenMantenimiento, *, actor_id: uuid.UUID, motivo: str
) -> OrdenMantenimiento:
    if not rules.puede_cancelar_orden(orden.estado):
        raise ReglaNegocio(f"la orden está {orden.estado}: no se puede cancelar")
    estado_antes = orden.estado
    orden.estado = "cancelada"
    activo = ActivoRepo(session).get(orden.activo_id)
    if estado_antes == "en_curso" and activo is not None and activo.estado == "en_mantenimiento":
        activo.estado = "operativo"
    auditoria.registrar(
        session,
        entidad="orden_mantenimiento",
        accion="cancelar",
        entidad_id=orden.id,
        usuario_id=actor_id,
        datos_antes={"estado": estado_antes},
        datos_despues={"estado": "cancelada", "motivo": motivo},
        empresa_id=activo.empresa_id if activo else None,
        sucursal_id=activo.sucursal_id if activo else None,
    )
    return orden


def q_ordenes(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    estado: str | None = None,
    activo_id: uuid.UUID | None = None,
):
    return OrdenMantenimientoRepo(session).q_list(empresa_id, estado=estado, activo_id=activo_id)


def q_de_activo(session: Session, activo_id: uuid.UUID):
    return OrdenMantenimientoRepo(session).q_de_activo(activo_id)
