"""Listeners: eventos operativos → asiento automático, según el mapeo
configurable en `regla_asiento` (`application/reglas.py`). Sin regla vigente
para la empresa+evento, o sin periodo contable abierto, el asiento se omite
(se loguea) — nunca bloquea el proceso de origen, mismo criterio que
`inventory.application.listeners`.

`purchases.comprobante_conforme` no genera asiento directamente — encola un
`movimiento_dinero` pendiente (`application/pagos.registrar_pago`); el asiento
se genera recién al ejecutar el pago (`application/pagos.ejecutar_pago`).

Cubre hoy los 4 eventos operativos que ya se publican en el código
(`purchases.oc_emitida`, `purchases.compra_recibida`, `sales.venta_confirmada`,
`purchases.comprobante_conforme`). El resto de eventos documentados en
`events.md` (pago registrado, comprobante emitido de venta, ajuste,
transferencia, caja chica...) no se generan aún porque los módulos de origen
todavía no los publican — ver ROADMAP, deuda técnica de accounting.
"""

import logging
import uuid
from datetime import date
from decimal import Decimal

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.accounting.application import asientos as asientos_uc
from src.modules.accounting.application import pagos as pagos_uc
from src.modules.users.infrastructure.models import Almacen, Sucursal

log = logging.getLogger(__name__)

# Inyectable (tests la reemplazan), mismo patrón que inventory.application.listeners.
session_factory = SessionLocal


def _empresa_de_almacen(session, almacen_id: str) -> uuid.UUID | None:
    almacen = session.get(Almacen, uuid.UUID(almacen_id))
    return almacen.empresa_id if almacen is not None else None


def _empresa_de_sucursal(session, sucursal_id: str) -> uuid.UUID | None:
    sucursal = session.get(Sucursal, uuid.UUID(sucursal_id))
    return sucursal.empresa_id if sucursal is not None else None


def _generar(session, *, empresa_id, evento, referencia_origen, monto, glosa) -> None:
    asiento = asientos_uc.crear_asiento_automatico_si_hay_regla(
        session,
        empresa_id=empresa_id,
        evento=evento,
        fecha=date.today(),
        glosa=glosa,
        referencia_origen=referencia_origen,
        monto=monto,
    )
    if asiento is None:
        log.info(
            "evento %s: sin regla_asiento configurada para empresa %s, asiento omitido",
            evento, empresa_id,
        )


def on_oc_emitida(payload: dict) -> None:
    try:
        with session_factory() as session:
            empresa_id = uuid.UUID(payload["empresa_id"])
            _generar(
                session,
                empresa_id=empresa_id,
                evento="purchases.oc_emitida",
                referencia_origen=payload["orden_compra_id"],
                monto=Decimal(payload["total"]),
                glosa=f"Provisión OC {payload['orden_compra_id']}",
            )
            session.commit()
    except Exception:
        log.exception("fallo generando asiento de OC %s", payload.get("orden_compra_id"))


def on_compra_recibida(payload: dict) -> None:
    try:
        with session_factory() as session:
            empresa_id = _empresa_de_almacen(session, payload["almacen_destino_id"])
            if empresa_id is None:
                log.warning(
                    "compra_recibida %s: almacén sin empresa, asiento omitido",
                    payload.get("orden_compra_id"),
                )
            else:
                monto = sum(
                    (
                        Decimal(it["cantidad"]) * Decimal(it["costo_unitario"])
                        for it in payload["items"]
                    ),
                    Decimal(0),
                )
                _generar(
                    session,
                    empresa_id=empresa_id,
                    evento="purchases.compra_recibida",
                    referencia_origen=payload["orden_compra_id"],
                    monto=monto,
                    glosa=f"Recepción OC {payload['orden_compra_id']}",
                )
            session.commit()
    except Exception:
        log.exception("fallo generando asiento de recepción %s", payload.get("orden_compra_id"))


def on_venta_confirmada(payload: dict) -> None:
    try:
        with session_factory() as session:
            empresa_id = _empresa_de_sucursal(session, payload["sucursal_id"])
            if empresa_id is None:
                log.warning(
                    "venta %s: sucursal sin empresa, asiento omitido", payload.get("venta_id")
                )
            else:
                _generar(
                    session,
                    empresa_id=empresa_id,
                    evento="sales.venta_confirmada",
                    referencia_origen=payload["venta_id"],
                    monto=Decimal(payload["total"]),
                    glosa=f"Venta {payload['venta_id']}",
                )
            session.commit()
    except Exception:
        log.exception("fallo generando asiento de venta %s", payload.get("venta_id"))


def on_comprobante_conforme(payload: dict) -> None:
    try:
        with session_factory() as session:
            monto_detraccion = None
            if payload.get("sujeto_spot") and payload.get("porcentaje_deteccion"):
                monto_detraccion = (
                    Decimal(payload["monto"]) * Decimal(payload["porcentaje_deteccion"]) / 100
                )
            pagos_uc.registrar_pago(
                session,
                empresa_id=uuid.UUID(payload["empresa_id"]),
                comprobante_id=uuid.UUID(payload["comprobante_id"]),
                proveedor_id=uuid.UUID(payload["proveedor_id"]),
                orden_compra_id=uuid.UUID(payload["orden_compra_id"]),
                monto=Decimal(payload["monto"]),
                monto_detraccion=monto_detraccion,
            )
            session.commit()
    except Exception:
        log.exception(
            "fallo encolando pago del comprobante %s", payload.get("comprobante_id")
        )


_registrado = False


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("purchases.oc_emitida", on_oc_emitida)
    event_bus.subscribe("purchases.compra_recibida", on_compra_recibida)
    event_bus.subscribe("sales.venta_confirmada", on_venta_confirmada)
    event_bus.subscribe("purchases.comprobante_conforme", on_comprobante_conforme)
