"""Traducción de una venta a la carga útil de Factiliza (catálogos SUNAT).

No importa el dominio de ningún módulo: recibe dataclasses neutras y
devuelve el JSON que espera la API. Toda la aritmética tributaria vive
acá, en un solo lugar.

Precios de entrada: lo que paga el cliente (IGV incluido, como se cotiza
en carta). El desglose valor/IGV se calcula hacia atrás.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from num2words import num2words

# Catálogo 51 — tipo de operación: venta interna.
TIPO_OPERACION_VENTA_INTERNA = "0101"
# Catálogo 01 — tipo de comprobante.
TIPO_DOC_FACTURA = "01"
TIPO_DOC_BOLETA = "03"
# Catálogo 07 — afectación al IGV.
AFECTACION_GRAVADO = "10"
AFECTACION_EXONERADO = "20"
# Catálogo 06 — tipo de documento de identidad del cliente.
DOC_SIN_RUC = "0"
DOC_DNI = "1"
DOC_CARNE_EXTRANJERIA = "4"
DOC_RUC = "6"
DOC_PASAPORTE = "7"
# Catálogo 52 — leyendas.
LEYENDA_MONTO_EN_LETRAS = "1000"
# Catálogo 01 — nota de crédito.
TIPO_DOC_NOTA_CREDITO = "07"
# Catálogo 09 — motivos de nota de crédito. Solo los que el negocio usa:
# el catálogo completo tiene trece y los otros son de casos que este ERP no
# produce (canje de vale, bonificación, ajuste de operaciones de exportación).
MOTIVO_NC_ANULACION = "01"
MOTIVO_NC_ANULACION_POR_ERROR_RUC = "02"
MOTIVO_NC_CORRECCION_DESCRIPCION = "03"
MOTIVO_NC_DEVOLUCION_TOTAL = "06"
MOTIVO_NC_DEVOLUCION_POR_ITEM = "07"
MOTIVOS_NC = {
    MOTIVO_NC_ANULACION: "Anulación de la operación",
    MOTIVO_NC_ANULACION_POR_ERROR_RUC: "Anulación por error en el RUC",
    MOTIVO_NC_CORRECCION_DESCRIPCION: "Corrección por error en la descripción",
    MOTIVO_NC_DEVOLUCION_TOTAL: "Devolución total",
    MOTIVO_NC_DEVOLUCION_POR_ITEM: "Devolución por ítem",
}
# Los que corrigen un dato del documento y no la operación: la venta ocurrió,
# el comprobante estaba mal. Habilitan reemitir el corregido.
MOTIVOS_NC_DE_CORRECCION = frozenset(
    {MOTIVO_NC_ANULACION_POR_ERROR_RUC, MOTIVO_NC_CORRECCION_DESCRIPCION}
)

_CENTIMOS = Decimal("0.01")


def _dos(valor: Decimal) -> Decimal:
    return valor.quantize(_CENTIMOS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Cliente:
    tipo_doc: str
    num_doc: str
    razon_social: str
    direccion: str = "-"


@dataclass(frozen=True)
class Item:
    codigo: str
    descripcion: str
    cantidad: Decimal
    # Precio unitario tal como lo paga el cliente, IGV incluido y ya neto
    # de descuento (Factiliza no recibe descuento por línea en este
    # endpoint; se aplica sobre el precio antes de llamar).
    precio_unitario: Decimal
    unidad: str = "NIU"


@dataclass(frozen=True)
class Documento:
    empresa_ruc: str
    tipo_doc: str
    serie: str
    correlativo: int
    fecha_emision: datetime
    cliente: Cliente
    items: list[Item]
    # Zona de Amazonía (Ley 27037): la venta sale exonerada de IGV.
    exonerado_igv: bool
    igv_porcentaje: Decimal = Decimal("18")
    moneda: str = "PEN"
    forma_pago: str = "Contado"
    metadatos: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentoAfectado:
    """El comprobante que la nota de crédito corrige (catálogo 01 + serie)."""

    tipo_doc: str
    serie: str
    correlativo: int

    @property
    def serie_correlativo(self) -> str:
        return f"{self.serie}-{self.correlativo}"


def monto_en_letras(monto: Decimal, moneda: str = "PEN") -> str:
    entero = int(monto)
    centavos = int((_dos(monto) - entero) * 100)
    unidad = "SOLES" if moneda == "PEN" else "DÓLARES AMERICANOS"
    letras = num2words(entero, lang="es").upper()
    return f"SON {letras} CON {centavos:02d}/100 {unidad}"


def _linea(item: Item, exonerado: bool, igv_pct: Decimal) -> dict:
    tasa = Decimal(0) if exonerado else igv_pct / Decimal(100)
    precio_unitario = _dos(item.precio_unitario)
    valor_unitario = _dos(precio_unitario / (Decimal(1) + tasa))
    valor_venta = _dos(valor_unitario * item.cantidad)
    igv = _dos(valor_venta * tasa)
    return {
        "unidad": item.unidad,
        "cantidad": float(item.cantidad),
        "cod_Producto": item.codigo,
        "descripcion": item.descripcion,
        "monto_Valor_Unitario": float(valor_unitario),
        "monto_Base_Igv": float(valor_venta),
        "porcentaje_Igv": float(Decimal(0) if exonerado else igv_pct),
        "igv": float(igv),
        "tip_Afe_Igv": AFECTACION_EXONERADO if exonerado else AFECTACION_GRAVADO,
        "total_Impuestos": float(igv),
        "monto_Precio_Unitario": float(precio_unitario),
        "monto_Valor_Venta": float(valor_venta),
        "factor_Icbper": 0,
    }


def construir_payload(doc: Documento) -> dict:
    """Arma el cuerpo de `POST /invoice/send`."""
    lineas = [_linea(i, doc.exonerado_igv, doc.igv_porcentaje) for i in doc.items]
    valor_venta = _dos(sum((Decimal(str(x["monto_Valor_Venta"])) for x in lineas), Decimal(0)))
    igv_total = _dos(sum((Decimal(str(x["igv"])) for x in lineas), Decimal(0)))
    total = _dos(valor_venta + igv_total)
    gravadas = Decimal(0) if doc.exonerado_igv else valor_venta
    exoneradas = valor_venta if doc.exonerado_igv else Decimal(0)

    return {
        "tipo_Operacion": TIPO_OPERACION_VENTA_INTERNA,
        "tipo_Doc": doc.tipo_doc,
        "serie": doc.serie,
        "correlativo": str(doc.correlativo),
        "tipo_Moneda": doc.moneda,
        "fecha_Emision": doc.fecha_emision.isoformat(),
        "empresa_Ruc": doc.empresa_ruc,
        "cliente_Tipo_Doc": doc.cliente.tipo_doc,
        "cliente_Num_Doc": doc.cliente.num_doc,
        "cliente_Razon_Social": doc.cliente.razon_social,
        "cliente_Direccion": doc.cliente.direccion,
        "monto_Oper_Gravadas": float(gravadas),
        "monto_Oper_Exoneradas": float(exoneradas),
        "monto_Igv": float(igv_total),
        "total_Impuestos": float(igv_total),
        "valor_Venta": float(valor_venta),
        "sub_Total": float(total),
        "monto_Imp_Venta": float(total),
        "estado_Documento": "0",
        "manual": False,
        "detalle": lineas,
        "forma_pago": [
            {
                "tipo": doc.forma_pago,
                "monto": float(total),
                "cuota": 0,
                "fecha_Pago": doc.fecha_emision.isoformat(),
            }
        ],
        "legend": [
            {
                "legend_Code": LEYENDA_MONTO_EN_LETRAS,
                "legend_Value": monto_en_letras(total, doc.moneda),
            }
        ],
    }


def construir_payload_nota_credito(
    doc: Documento,
    afectado: DocumentoAfectado,
    motivo_cod: str,
    motivo_descripcion: str | None = None,
) -> dict:
    """Arma el cuerpo de `POST /note/send`.

    Misma aritmética que el comprobante que corrige —la nota de crédito
    también declara valor de venta, IGV y total— más los tres campos que la
    vuelven una nota: qué documento afecta y por qué (catálogo 09).

    Los ítems son los que se acreditan: la NC total lleva todos, la parcial
    solo los devueltos con su cantidad. El monto sale de esas líneas, así
    que no hay un total que pueda contradecir al detalle.
    """
    if motivo_cod not in MOTIVOS_NC:
        raise ValueError(f"motivo de nota de crédito fuera del catálogo 09: {motivo_cod}")
    payload = construir_payload(doc)
    payload["tipo_Doc"] = TIPO_DOC_NOTA_CREDITO
    payload["afectado_Tipo_Doc"] = afectado.tipo_doc
    payload["afectado_Num_Doc"] = afectado.serie_correlativo
    payload["motivo_Cod"] = motivo_cod
    payload["motivo_Descripcion"] = motivo_descripcion or MOTIVOS_NC[motivo_cod]
    # La forma de pago es del documento original: una nota de crédito no
    # cobra nada, y mandarla confunde la lectura del XML.
    payload.pop("forma_pago", None)
    return payload
