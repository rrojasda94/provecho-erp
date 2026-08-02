"""Precuenta: lo que el cliente pide antes de pagar (RN-COM-019).

**No es un comprobante.** No tiene serie ni correlativo, no se envía a
SUNAT y no cambia el estado de la venta: es el papel que el mesero deja en
la mesa para que el cliente revise el consumo. El comprobante fiscal nace
recién al cobrar.

Se imprime tantas veces como haga falta y no se audita: pedirla dos veces
es normal, no una señal de nada.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.sales.application.errors import NoEncontrado
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import (
    Mesa,
    ProductoComercial,
    Venta,
    VentaItem,
)

ANCHO = 40


def _linea_monto(etiqueta: str, monto: Decimal) -> str:
    """Etiqueta a la izquierda, monto pegado al borde derecho."""
    texto = f"S/ {monto:.2f}"
    return f"{etiqueta}{texto.rjust(ANCHO - len(etiqueta))}"


def generar(session: Session, venta_id: uuid.UUID, grupo_cobro: int | None = None) -> dict:
    """Texto plano para impresora térmica. Con `grupo_cobro` imprime solo esa
    cuenta — el caso de la mesa que se divide y cada uno quiere ver lo suyo.
    """
    venta = session.get(Venta, venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")

    consulta = select(VentaItem, ProductoComercial).join(
        ProductoComercial, ProductoComercial.id == VentaItem.producto_comercial_id
    ).where(VentaItem.venta_id == venta_id)
    if grupo_cobro is not None:
        consulta = consulta.where(VentaItem.grupo_cobro == grupo_cobro)
    pares = list(session.execute(consulta))

    encabezado = f"ORDEN #{venta.numero_orden}"
    if venta.mesa_id:
        mesa = session.get(Mesa, venta.mesa_id)
        if mesa is not None:
            encabezado += f" - MESA {mesa.numero}"
    if grupo_cobro is not None:
        encabezado += f" - CUENTA {grupo_cobro}"

    lineas = [
        "=" * ANCHO,
        encabezado.center(ANCHO),
        "PRECUENTA".center(ANCHO),
        "NO ES COMPROBANTE DE PAGO".center(ANCHO),
        f"{venta.created_at:%d/%m/%Y %H:%M}".center(ANCHO),
        "=" * ANCHO,
    ]
    subtotal = Decimal(0)
    for it, prod in pares:
        importe = it.cantidad * it.precio_unitario - it.descuento
        subtotal += importe
        lineas.append(
            _linea_monto(f"{it.cantidad.normalize()}x {prod.nombre}"[:26], importe)
        )
    lineas.append("-" * ANCHO)
    lineas.append(_linea_monto("Subtotal", subtotal))

    descuento = (
        rules.descuento_prorrateado(
            venta.descuento_modo,
            venta.descuento_valor,
            rules.total_venta(
                [
                    (f.cantidad, f.precio_unitario, f.descuento)
                    for f in session.scalars(
                        select(VentaItem).where(VentaItem.venta_id == venta_id)
                    )
                ]
            ),
            subtotal,
        )
        if venta.descuento_modo
        else Decimal(0)
    )
    if descuento:
        lineas.append(_linea_monto(f"Descuento ({venta.descuento_motivo})", -descuento))
    lineas.append(_linea_monto("TOTAL", subtotal - descuento))
    lineas += ["=" * ANCHO, "Gracias por su visita".center(ANCHO)]

    return {
        "venta_id": str(venta_id),
        "grupo_cobro": grupo_cobro,
        "total": subtotal - descuento,
        "texto": "\n".join(lineas),
    }
