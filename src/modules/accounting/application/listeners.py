"""Listeners: eventos operativos → asiento automático, según el mapeo
configurable en `regla_asiento` (`application/reglas.py`). Sin regla vigente
para la empresa+evento, o sin periodo contable abierto, el asiento se omite
(se loguea) — nunca bloquea el proceso de origen, mismo criterio que
`inventory.application.listeners`.

`purchases.comprobante_conforme` no genera asiento directamente — encola un
`movimiento_dinero` pendiente (`application/pagos.registrar_pago`); el asiento
se genera recién al ejecutar el pago (`application/pagos.ejecutar_pago`).

Cubre hoy 6 eventos operativos: `purchases.oc_emitida`,
`purchases.compra_recibida`, `sales.venta_confirmada`,
`purchases.comprobante_conforme`, `inventory.transferencia_recibida` —que
solo asienta cuando el traslado llegó con faltante— y
`inventory.consumo_personal_valorizado`, la comida del personal llevada a
gasto (RN-COM-025), que se reversa con
`inventory.consumo_personal_reversado` si el consumo se anula. El resto de
los documentados en `events.md` (pago
registrado, comprobante emitido de venta, ajuste, caja chica...) no se
generan aún porque los módulos de origen todavía no los publican — ver
ROADMAP, deuda técnica de accounting.
"""

import logging
import uuid
from decimal import Decimal

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.accounting.application import asientos as asientos_uc
from src.modules.accounting.application import pagos as pagos_uc
from src.modules.users.infrastructure.models import Almacen, Sucursal
from src.shared import fechas

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
        fecha=fechas.hoy(),
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


def on_consumo_personal_valorizado(payload: dict) -> None:
    """Comida del personal → gasto de alimentación de personal (RN-COM-025).

    El monto lo valoriza `inventory` a costo promedio, igual que la merma:
    acá no se recalcula nada, o el gasto contable diría un número distinto
    al que salió del almacén. La empresa mapea las cuentas (gasto / salida
    de existencias) en su `regla_asiento`.
    """
    try:
        with session_factory() as session:
            empresa_id = payload.get("empresa_id") or _empresa_de_sucursal(
                session, payload["sucursal_id"]
            )
            if empresa_id is None:
                log.warning(
                    "consumo de personal %s: sin empresa, asiento omitido",
                    payload.get("venta_id"),
                )
            else:
                motivo = payload.get("motivo") or "sin motivo"
                _generar(
                    session,
                    empresa_id=uuid.UUID(str(empresa_id)),
                    evento="inventory.consumo_personal_valorizado",
                    referencia_origen=payload["venta_id"],
                    monto=Decimal(payload["monto"]),
                    glosa=f"Consumo de personal ({motivo}) {payload['venta_id']}",
                )
            session.commit()
    except Exception:
        log.exception(
            "fallo generando asiento de consumo de personal %s",
            payload.get("venta_id"),
        )


def on_consumo_personal_reversado(payload: dict) -> None:
    """El consumo se anuló y el insumo volvió al almacén: el gasto también
    tiene que volver, o queda inflado por algo que nadie comió."""
    try:
        with session_factory() as session:
            empresa_id = payload.get("empresa_id")
            if empresa_id is not None:
                asientos_uc.anular_asiento_por_origen(
                    session,
                    empresa_id=uuid.UUID(str(empresa_id)),
                    evento="inventory.consumo_personal_valorizado",
                    referencia_origen=payload["venta_id"],
                )
            session.commit()
    except Exception:
        log.exception(
            "fallo reversando el asiento de consumo de personal %s",
            payload.get("venta_id"),
        )


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


def on_transferencia_recibida(payload: dict) -> None:
    """Un traslado entre almacenes de la misma empresa **no mueve
    resultado**: la mercadería cambia de sitio, no de dueño. Lo que sí es un
    hecho contable es la **diferencia**: lo que salió del origen y no llegó
    al destino se perdió en el camino, y eso es gasto.

    Por eso el asiento se genera solo cuando hay faltante. Sin diferencias
    no hay nada que registrar, y un asiento por cada transferencia llenaría
    el libro de movimientos que se cancelan entre sí.
    """
    try:
        diferencias = payload.get("diferencias") or []
        monto = Decimal(payload.get("monto_diferencia") or 0)
        if not diferencias or monto <= 0:
            return
        with session_factory() as session:
            empresa_id = _empresa_de_almacen(session, payload["origen_almacen_id"])
            if empresa_id is None:
                log.warning(
                    "transferencia %s: almacén sin empresa, asiento omitido",
                    payload.get("transferencia_id"),
                )
            else:
                _generar(
                    session,
                    empresa_id=empresa_id,
                    evento="inventory.transferencia_recibida",
                    referencia_origen=payload["transferencia_id"],
                    monto=monto,
                    glosa=(
                        f"Faltante en traslado {payload['transferencia_id']} "
                        f"({len(diferencias)} ítem/s)"
                    ),
                )
            session.commit()
    except Exception:
        log.exception(
            "fallo generando asiento de traslado %s", payload.get("transferencia_id")
        )


def on_merma_registrada(payload: dict) -> None:
    """La merma desechada **sí** es pérdida: mercadería que se compró y que
    no va a vender nada (RN-INV-017).

    Llega recién al desechar, no al apartar: mientras la auditoría no
    decide, la mercadería sigue ahí y puede volver al estante — asentarla
    antes obligaría a reversar la mitad de los asientos.
    """
    try:
        monto = Decimal(payload.get("monto") or 0)
        if monto <= 0:
            # Sin costo promedio cargado no hay importe que asentar. El
            # movimiento de stock ya quedó; esto solo evita un asiento en 0.
            return
        with session_factory() as session:
            empresa_id = _empresa_de_almacen(session, payload["almacen_id"])
            if empresa_id is None:
                log.warning("merma en almacén sin empresa, asiento omitido")
            else:
                _generar(
                    session,
                    empresa_id=empresa_id,
                    evento="inventory.merma_registrada",
                    referencia_origen=payload["sku_id"],
                    monto=monto,
                    glosa=f"Merma desechada por {payload['motivo']}",
                )
            session.commit()
    except Exception:
        log.exception("fallo generando asiento de merma de %s", payload.get("sku_id"))


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
    event_bus.subscribe(
        "inventory.transferencia_recibida", on_transferencia_recibida
    )
    event_bus.subscribe("inventory.merma_registrada", on_merma_registrada)
    event_bus.subscribe(
        "inventory.consumo_personal_valorizado", on_consumo_personal_valorizado
    )
    event_bus.subscribe(
        "inventory.consumo_personal_reversado", on_consumo_personal_reversado
    )
