"""Casos de uso de orden de producción: crear (borrador) → registrar
consumo (en_proceso) → completar (conforme | no_conforme_reprocesado |
no_conforme_desechado).

`plan_produccion` (cronograma) queda diferido — la orden se crea ad-hoc,
sin plan (deuda técnica, ver ROADMAP).
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.inventory.infrastructure.models import Articulo, Receta
from src.modules.production.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.production.domain import rules
from src.modules.production.infrastructure.models import (
    ConsumoProduccionItem,
    OrdenProduccion,
)
from src.modules.production.infrastructure.repositories import OrdenProduccionRepo
from src.modules.users.infrastructure.models import Almacen


def crear_orden_produccion(
    session: Session,
    *,
    articulo_id: uuid.UUID,
    almacen_id: uuid.UUID,
    cantidad_planeada: Decimal,
    creado_por: uuid.UUID,
    idempotency_key: str,
) -> OrdenProduccion:
    repo = OrdenProduccionRepo(session)
    existente = repo.get_by_idempotency(idempotency_key)
    if existente is not None:
        return existente

    if session.get(Articulo, articulo_id) is None:
        raise NoEncontrado(f"artículo {articulo_id} no encontrado")
    if session.get(Almacen, almacen_id) is None:
        raise NoEncontrado(f"almacén {almacen_id} no encontrado")
    if Decimal(str(cantidad_planeada)) <= 0:
        raise ReglaNegocio("cantidad_planeada debe ser > 0")
    if session.scalar(select(Receta).where(Receta.articulo_id == articulo_id)) is None:
        raise ReglaNegocio(f"artículo {articulo_id} no tiene receta de subreceta definida")

    return repo.add(
        OrdenProduccion(
            articulo_id=articulo_id,
            almacen_id=almacen_id,
            cantidad_planeada=Decimal(str(cantidad_planeada)),
            estado="borrador",
            creado_por=creado_por,
            idempotency_key=idempotency_key,
        )
    )


def registrar_consumo(
    session: Session,
    orden_id: uuid.UUID,
    *,
    # [{articulo_id, cantidad, costo_unitario, peso_desperdicio_real, tipo_desperdicio}]
    items: list[dict],
) -> OrdenProduccion:
    orden = OrdenProduccionRepo(session).get(orden_id)
    if orden is None:
        raise NoEncontrado("orden de producción no encontrada")
    if not rules.puede_registrar_consumo(orden.estado):
        raise Conflicto(f"la orden está {orden.estado}; no admite registrar consumo")
    if not items:
        raise ReglaNegocio("una orden requiere al menos un ítem de consumo")

    evento_items = []
    for it in items:
        if session.get(Articulo, it["articulo_id"]) is None:
            raise NoEncontrado(f"artículo {it['articulo_id']} no encontrado")
        cantidad = Decimal(str(it["cantidad"]))
        if cantidad <= 0:
            raise ReglaNegocio("cantidad de consumo debe ser > 0")
        costo_unitario = Decimal(str(it["costo_unitario"]))
        session.add(
            ConsumoProduccionItem(
                orden_produccion_id=orden.id,
                articulo_id=it["articulo_id"],
                cantidad=cantidad,
                costo_unitario=costo_unitario,
                peso_desperdicio_real=Decimal(str(it.get("peso_desperdicio_real", 0))),
                tipo_desperdicio=it.get("tipo_desperdicio"),
            )
        )
        evento_items.append(
            {"articulo_id": str(it["articulo_id"]), "cantidad": str(cantidad)}
        )

    orden.estado = "en_proceso"
    session.flush()
    event_bus.publish(
        "production.consumo_registrado",
        {
            "orden_produccion_id": str(orden.id),
            "almacen_id": str(orden.almacen_id),
            "items": evento_items,
        },
        session=session,
    )
    return orden


def completar_orden_produccion(
    session: Session,
    orden_id: uuid.UUID,
    *,
    resultado: str,
    costo_hora_mano_obra: Decimal,
    cantidad_producida: Decimal | None = None,
    horas_hombre: Decimal | None = None,
    merma_cantidad: Decimal | None = None,
    merma_motivo: str | None = None,
    evidencia_destruccion_url: str | None = None,
) -> OrdenProduccion:
    orden = OrdenProduccionRepo(session).get(orden_id)
    if orden is None:
        raise NoEncontrado("orden de producción no encontrada")
    if not rules.puede_completar(orden.estado):
        raise Conflicto(f"la orden está {orden.estado}; no admite completarse")
    if resultado not in rules.RESULTADOS_CONTROL_CALIDAD:
        raise ReglaNegocio(f"resultado de control de calidad inválido: {resultado}")

    costo_insumos = sum(
        (c.cantidad * c.costo_unitario for c in OrdenProduccionRepo(session).consumos(orden.id)),
        Decimal(0),
    )
    horas_hombre = Decimal(str(horas_hombre)) if horas_hombre is not None else Decimal(0)
    costo_mano_obra = horas_hombre * costo_hora_mano_obra
    orden.horas_hombre = horas_hombre
    orden.costo_insumos = costo_insumos
    orden.costo_mano_obra = costo_mano_obra

    if resultado == "conforme":
        if not cantidad_producida or Decimal(str(cantidad_producida)) <= 0:
            raise ReglaNegocio("resultado 'conforme' requiere cantidad_producida > 0")
        cantidad_producida = Decimal(str(cantidad_producida))
        orden.cantidad_producida = cantidad_producida
        orden.costo_real_unitario = rules.costo_real_unitario(
            costo_insumos, costo_mano_obra, cantidad_producida
        )
        orden.estado = "conforme"
        event_bus.publish(
            "production.orden_completada",
            {
                "orden_produccion_id": str(orden.id),
                "almacen_id": str(orden.almacen_id),
                "articulo_id": str(orden.articulo_id),
                "cantidad_producida": str(cantidad_producida),
                "costo_unitario": str(orden.costo_real_unitario),
            },
            session=session,
        )
    else:
        if resultado == "no_conforme_desechado":
            if not merma_cantidad or Decimal(str(merma_cantidad)) <= 0:
                raise ReglaNegocio("desecho requiere merma_cantidad > 0")
            if not merma_motivo:
                raise ReglaNegocio("desecho requiere merma_motivo")
            if not evidencia_destruccion_url:
                raise ReglaNegocio("desecho requiere evidencia_destruccion_url (RN-PRD-015)")
            orden.merma_cantidad = Decimal(str(merma_cantidad))
            orden.merma_motivo = merma_motivo
            orden.evidencia_destruccion_url = evidencia_destruccion_url
        orden.estado = resultado
        event_bus.publish(
            "production.no_conformidad_detectada",
            {"orden_produccion_id": str(orden.id), "resultado": resultado},
            session=session,
        )
    return orden
