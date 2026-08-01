"""Ciclo de caja (PROC-CTB-001/002): apertura, cierre, arqueo.

**Slice mínimo**, no el proceso completo: crea y concilia los tres
registros con sus campos núcleo, para alimentar el dashboard gerencial y
dejar un cierre con verificación real (no solo números que alguien tipeó).

Diferido a un slice dedicado (ver ROADMAP): validación completa RN-POS-009
a RN-POS-013 (verificación de series de POS, denominaciones obligatorias,
relevo autenticado por ambas partes con PIN — hoy se registra el
`relevo_encargado_id` sin exigir su propia autenticación), la cadena de
custodia de `custodia_efectivo` como máquina de estados, y el enlace con
`sales` para bloquear el cobro si no hay caja abierta.

`accounting` no importa el dominio de `sales` (CLAUDE.md): el monto
esperado del cierre se reconcilia vía el contrato público
`sales.application.queries_publicas.total_efectivo_cobrado`, nunca
importando `Venta`/`Pago` directo.
"""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.accounting.application.errors import Conflicto, NoEncontrado
from src.modules.accounting.infrastructure.models import (
    AperturaCaja,
    Arqueo,
    CierreCaja,
    MovimientoCaja,
)
from src.modules.accounting.infrastructure.repositories import (
    AperturaCajaRepo,
    ArqueoRepo,
    CierreCajaRepo,
    MovimientoCajaRepo,
)
from src.modules.sales.application.queries_publicas import (
    puntos_venta_de_empresa,
    total_efectivo_cobrado,
)


def abrir_caja(
    session: Session,
    *,
    punto_venta_id: uuid.UUID,
    cajero_id: uuid.UUID,
    relevo_encargado_id: uuid.UUID,
    monto_apertura: Decimal,
    detalle_denominaciones: dict | None = None,
    diferencia_reportada: Decimal | None = None,
) -> AperturaCaja:
    repo = AperturaCajaRepo(session)
    if repo.abierta_en(punto_venta_id) is not None:
        raise Conflicto("ya hay una caja abierta en este punto de venta")

    apertura = repo.add(
        AperturaCaja(
            punto_venta_id=punto_venta_id,
            cajero_id=cajero_id,
            relevo_encargado_id=relevo_encargado_id,
            monto_apertura=monto_apertura,
            detalle_denominaciones=detalle_denominaciones,
            diferencia_reportada=diferencia_reportada,
        )
    )
    event_bus.publish(
        "accounting.apertura_caja_registrada",
        {
            "apertura_caja_id": str(apertura.id),
            "punto_venta_id": str(punto_venta_id),
            "diferencia_reportada": str(diferencia_reportada) if diferencia_reportada else None,
        },
    )
    return apertura


def registrar_movimiento_caja(
    session: Session,
    apertura_caja_id: uuid.UUID,
    *,
    tipo: str,
    monto: Decimal,
    motivo: str,
    registrado_por: uuid.UUID,
    idempotency_key: str,
    autorizado_por: uuid.UUID | None = None,
) -> MovimientoCaja:
    """Ingreso o retiro de efectivo del cajón durante el turno (RN-MDP-007).

    El turno real no es solo vender: se le paga al repartidor, se compra
    hielo, entra el vuelto que faltaba. Sin registrarlo, el cierre cuadra
    contra un esperado irreal y el descuadre se le atribuye al cajero.

    **Retirar exige autorización de supervisor**; ingresar no: meter plata
    al cajón no es la operación de la que hay que desconfiar.
    """
    repo = MovimientoCajaRepo(session)
    existente = repo.get_by_idempotency(idempotency_key)
    if existente is not None:
        return existente

    apertura = AperturaCajaRepo(session).get(apertura_caja_id)
    if apertura is None:
        raise NoEncontrado("apertura de caja no encontrada")
    if CierreCajaRepo(session).get_by_apertura(apertura_caja_id) is not None:
        raise Conflicto("la caja ya está cerrada; no admite movimientos")
    if tipo not in ("ingreso", "retiro"):
        raise Conflicto(f"tipo de movimiento inválido: {tipo}")
    if monto <= 0:
        raise Conflicto("el monto debe ser > 0")
    if not (motivo or "").strip():
        raise Conflicto("el movimiento de efectivo requiere motivo")
    if tipo == "retiro" and autorizado_por is None:
        raise Conflicto("retirar efectivo requiere autorización de supervisor")

    if tipo == "retiro":
        # No se puede sacar más de lo que hay: el cajón no da crédito.
        disponible = (
            apertura.monto_apertura
            + total_efectivo_cobrado(
                session, apertura.punto_venta_id, apertura.created_at
            )
            + repo.neto(apertura_caja_id)
        )
        if monto > disponible:
            raise Conflicto(
                f"el retiro excede el efectivo en caja ({disponible})"
            )

    movimiento = repo.add(
        MovimientoCaja(
            apertura_caja_id=apertura_caja_id,
            tipo=tipo,
            monto=monto,
            motivo=motivo.strip(),
            registrado_por=registrado_por,
            autorizado_por=autorizado_por,
            idempotency_key=idempotency_key,
        )
    )
    event_bus.publish(
        "accounting.movimiento_caja_registrado",
        {
            "movimiento_caja_id": str(movimiento.id),
            "apertura_caja_id": str(apertura_caja_id),
            "tipo": tipo,
            "monto": str(monto),
            "motivo": movimiento.motivo,
        },
    )
    return movimiento


def cerrar_caja(
    session: Session,
    apertura_caja_id: uuid.UUID,
    *,
    cajero_id: uuid.UUID,
    monto_real: Decimal,
    custodia: str,
    descuadre_atribucion: str | None = None,
) -> CierreCaja:
    apertura = AperturaCajaRepo(session).get(apertura_caja_id)
    if apertura is None:
        raise NoEncontrado("apertura de caja no encontrada")
    if CierreCajaRepo(session).get_by_apertura(apertura_caja_id) is not None:
        raise Conflicto("esta apertura ya tiene un cierre registrado")

    efectivo_cobrado = total_efectivo_cobrado(
        session, apertura.punto_venta_id, apertura.created_at
    )
    # Ingresos y retiros del turno: sin ellos el esperado es irreal y todo
    # descuadre se le carga al cajero (RN-MDP-007).
    movimientos = MovimientoCajaRepo(session).neto(apertura_caja_id)
    monto_esperado = apertura.monto_apertura + efectivo_cobrado + movimientos
    descuadre = monto_real - monto_esperado
    estado = "conforme" if descuadre == 0 else "con_irregularidad"

    cierre = CierreCajaRepo(session).add(
        CierreCaja(
            apertura_caja_id=apertura_caja_id,
            cajero_id=cajero_id,
            montos_esperados={
            "efectivo": str(monto_esperado),
            "apertura": str(apertura.monto_apertura),
            "cobrado": str(efectivo_cobrado),
            "movimientos": str(movimientos),
        },
            montos_reales={"efectivo": str(monto_real)},
            descuadre_monto=descuadre,
            descuadre_atribucion=descuadre_atribucion if descuadre != 0 else None,
            custodia=custodia,
            estado=estado,
        )
    )
    event_bus.publish(
        "accounting.cierre_caja_registrado",
        {
            "cierre_caja_id": str(cierre.id),
            "apertura_caja_id": str(apertura_caja_id),
            "descuadre_monto": str(descuadre),
        },
    )
    if estado == "con_irregularidad":
        event_bus.publish(
            "accounting.cierre_caja_irregular",
            {
                "cierre_caja_id": str(cierre.id),
                "descuadre_monto": str(descuadre),
                "descuadre_atribucion": descuadre_atribucion,
            },
        )
    return cierre


def registrar_arqueo(
    session: Session,
    *,
    punto_venta_id: uuid.UUID,
    tipo: str,
    realizado_por: uuid.UUID,
    monto_contado: Decimal,
) -> Arqueo:
    apertura = AperturaCajaRepo(session).abierta_en(punto_venta_id)
    if apertura is None:
        raise NoEncontrado("no hay caja abierta en este punto de venta")

    efectivo_cobrado = total_efectivo_cobrado(session, punto_venta_id, apertura.created_at)
    monto_esperado = apertura.monto_apertura + efectivo_cobrado
    diferencia = monto_contado - monto_esperado

    arqueo = ArqueoRepo(session).add(
        Arqueo(
            punto_venta_id=punto_venta_id,
            tipo=tipo,
            realizado_por=realizado_por,
            monto_esperado=monto_esperado,
            monto_contado=monto_contado,
            diferencia=diferencia,
        )
    )
    event_bus.publish(
        "accounting.arqueo_registrado",
        {
            "arqueo_id": str(arqueo.id),
            "punto_venta_id": str(punto_venta_id),
            "diferencia_monto": str(diferencia),
        },
    )
    return arqueo


def cajas_abiertas(session: Session, empresa_id: uuid.UUID) -> list[dict]:
    """Estado actual de caja por punto de venta de la empresa — para el
    dashboard gerencial (`core.dashboard_router`)."""
    punto_venta_ids = puntos_venta_de_empresa(session, empresa_id)
    aperturas = AperturaCajaRepo(session).abiertas_de(punto_venta_ids)
    return [
        {
            "apertura_caja_id": a.id,
            "punto_venta_id": a.punto_venta_id,
            "cajero_id": a.cajero_id,
            "monto_apertura": a.monto_apertura,
            "abierta_desde": a.created_at,
        }
        for a in aperturas
    ]
