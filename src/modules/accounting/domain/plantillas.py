"""Plantillas de asiento del PCGE: cómo se escribe en cuentas oficiales cada
hecho operativo que el ERP ya publica como evento.

**Por qué existen.** `regla_asiento` mapea un evento a **una** cuenta de debe
y **una** de haber. Eso alcanza para un asiento de dos líneas y no alcanza
para los asientos reales del Perú: una compra recibida son cuatro (compra,
deuda, y el asiento de destino que ingresa la mercadería al almacén), y el
IGV suma las suyas. Estas plantillas son ese asiento completo, escrito con
los códigos del PCGE (`domain/pcge.py`).

**Quién gana.** La empresa manda: si tiene una `regla_asiento` vigente para
el evento, se usa esa y estas plantillas no se miran. La plantilla es el
*default de fábrica* para quien no configuró nada — antes de esto, no
configurar nada significaba no tener asiento.

**El IGV nace con el comprobante, no con la operación.** Ni la venta al
confirmarse ni la compra al recibirse llevan IGV en su asiento: lo reconoce
el asiento del comprobante (`sales.comprobante_emitido`,
`purchases.comprobante_conforme`). No es un rodeo — es lo que exige el marco
legal del área: el crédito fiscal se toma con el comprobante válido y anotado
en el registro de compras, y el débito nace con el comprobante emitido. De
paso resuelve un problema de orden: la casilla «operación gravada» vive en el
comprobante, que todavía no existe cuando se confirma la venta o se recibe la
mercadería. Con IGV exonerado los dos asientos quedan en cero y no se
escriben.

**El circuito es el de mercaderías** (601 → 201 → 611 → 691 / 7011) y no el
de producción (602 → 241 → 21 → 702). Un restaurante transforma insumos, así
que el circuito de producción sería el purista; el de mercaderías es el que
puede sostenerse sin un sistema de costos por orden, que el ERP no lleva. La
empresa que quiera el otro lo dice en su `regla_asiento`.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENTIMO = Decimal("0.01")


@dataclass(frozen=True)
class LineaPlantilla:
    """Una línea del asiento: qué cuenta, de qué lado y con cuál importe."""

    codigo: str
    tipo: str  # "debe" | "haber"
    importe: str  # "base" | "igv" | "total"


@dataclass(frozen=True)
class Plantilla:
    """`monto_es` dice qué trae el evento en su campo de monto, que es lo
    único que el emisor sabe y contabilidad no puede adivinar:

    - `total` — importe cobrado al cliente, IGV incluido (una venta);
    - `base` — valor sin IGV (una compra: `costo_unitario` es el costo que
      `inventory` usa para valorizar, y el IGV de compras es crédito fiscal,
      no costo);
    - `neto` — importe sin IGV aplicable (un costo ya valorizado, un pago).
    """

    monto_es: str
    lineas: tuple[LineaPlantilla, ...]


def _d(codigo: str, importe: str = "total") -> LineaPlantilla:
    return LineaPlantilla(codigo, "debe", importe)


def _h(codigo: str, importe: str = "total") -> LineaPlantilla:
    return LineaPlantilla(codigo, "haber", importe)


PLANTILLAS: dict[str, Plantilla] = {
    # Venta: nace la cuenta por cobrar del cliente. El cobro la cancela
    # contra caja o bancos — hoy `sales.pago_registrado` todavía no se
    # publica, así que 1212 queda abierta (deuda anotada en ROADMAP).
    #
    # **Sin IGV**: al confirmar la orden todavía no existe el comprobante, y
    # el débito fiscal nace con él. Ver `sales.comprobante_emitido`.
    "sales.venta_confirmada": Plantilla(
        monto_es="total",
        lineas=(
            _d("1212", "total"),
            _h("7011", "total"),
        ),
    ),
    # Comprobante emitido: el débito fiscal. Reclasifica del ingreso al
    # pasivo tributario la parte que nunca fue de la empresa. Exonerada, el
    # IGV vale cero y este asiento no se escribe.
    "sales.comprobante_emitido": Plantilla(
        monto_es="total",
        lineas=(
            _d("7011", "igv"),
            _h("40111", "igv"),
        ),
    ),
    # Compra recibida: el asiento de compra y el de destino en un solo
    # comprobante, que es como lo lleva cualquier contador peruano. Sin el
    # de destino la mercadería nunca entra al activo y el elemento 6 queda
    # con un gasto que ya no lo es.
    #
    # **Sin IGV**: al recibir la mercadería todavía no hay comprobante
    # conforme, y el crédito fiscal solo se toma con el comprobante válido y
    # anotado (marco legal del área). Ver `purchases.comprobante_conforme`.
    "purchases.compra_recibida": Plantilla(
        monto_es="base",
        lineas=(
            _d("6011", "base"),
            _h("4212", "base"),
            _d("201", "base"),
            _h("611", "base"),
        ),
    ),
    # Comprobante de compra conforme: el crédito fiscal. Sube la deuda con
    # el proveedor de la base al total de su factura y abre el IGV a favor.
    "purchases.comprobante_conforme": Plantilla(
        monto_es="base",
        lineas=(
            _d("40111", "igv"),
            _h("4212", "igv"),
        ),
    ),
    # Comida del personal (RN-COM-025, ADR-034): sale del almacén y va a
    # atención al personal, no a costo de ventas.
    "inventory.consumo_personal_valorizado": Plantilla(
        monto_es="neto",
        lineas=(_d("625"), _h("201")),
    ),
    # Merma desechada y faltante de traslado: existencias que salieron y no
    # se convirtieron en venta.
    "inventory.merma_registrada": Plantilla(
        monto_es="neto",
        lineas=(_d("6599"), _h("201")),
    ),
    "inventory.transferencia_recibida": Plantilla(
        monto_es="neto",
        lineas=(_d("6599"), _h("201")),
    ),
    # Pago a proveedor: cancela la deuda contra la cuenta corriente. La
    # detracción no abre línea propia — el dinero sale igual de la misma
    # cuenta, solo cambia el banco de destino (ver README).
    "accounting.pago_ejecutado": Plantilla(
        monto_es="neto",
        lineas=(_d("4212"), _h("1041")),
    ),
}
# `purchases.oc_emitida` no tiene plantilla a propósito: una orden emitida es
# un compromiso, no un hecho contable — su lugar en el PCGE son las cuentas
# de orden (elemento 0), que este catálogo no siembra. Quien igual quiera
# provisionarla lo declara en su `regla_asiento`.


def desagregar(monto: Decimal, tasa_igv: Decimal, monto_es: str) -> dict[str, Decimal]:
    """Base, IGV y total del hecho, redondeados al céntimo.

    El IGV se calcula por diferencia contra el total y nunca al revés: si se
    redondean base e IGV por separado, la suma se aparta del importe que el
    cliente pagó o que el proveedor facturó, y el asiento no cuadra por un
    céntimo.
    """
    monto = Decimal(monto)
    if monto_es == "neto" or tasa_igv == 0:
        return {"base": monto, "igv": Decimal(0), "total": monto}
    factor = Decimal(1) + tasa_igv / Decimal(100)
    if monto_es == "total":
        base = (monto / factor).quantize(CENTIMO, rounding=ROUND_HALF_UP)
        return {"base": base, "igv": monto - base, "total": monto}
    total = (monto * factor).quantize(CENTIMO, rounding=ROUND_HALF_UP)
    return {"base": monto, "igv": total - monto, "total": total}
