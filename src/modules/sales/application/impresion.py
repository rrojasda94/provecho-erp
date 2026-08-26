"""Lo que se manda a la ticketera de 80 mm: encabezado de marca y ticket del
comprobante (ADR-067).

Dos piezas:

- `encabezado()` — quién emite. Es el mismo para la comanda, la precuenta y
  el comprobante: logo de la marca, razón social y RUC de la empresa, y
  nombre y dirección de la sucursal. Se resuelve del padrón (`marca`,
  `empresa`, `sucursal`) y no se teclea por local: un local que escribe su
  propio encabezado termina imprimiendo el RUC de la empresa equivocada, y
  eso en una boleta es un problema fiscal, no de diseño.

- `ticket_comprobante()` — el cuerpo fiscal. **No recalcula nada**: pide el
  mismo payload que se le manda a Factiliza (`documento_de` +
  `construir_payload`) y lo lee. Si el ticket sumara por su cuenta, el papel
  y el XML podrían discrepar en un céntimo de redondeo, y el papel es lo que
  el cliente se lleva.

Se imprime **aunque el comprobante siga pendiente** de llegar a SUNAT: la
emisión es asíncrona a propósito (RN-COM-003) y hacer esperar al cliente en
caja a que conteste un tercero es exactamente lo que esa decisión evita. El
ticket lo dice en su franja mientras no esté aceptado.
"""

import uuid
from decimal import Decimal

import segno
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.modules.sales.application import comprobantes
from src.modules.sales.application.errors import Conflicto, NoEncontrado
from src.modules.sales.domain import qr_sunat
from src.modules.sales.infrastructure.repositories import ComprobanteRepo, VentaRepo
from src.shared.integrations import factiliza
from src.shared.models import Comprobante

# Los que tienen representación impresa propia hoy. La nota de crédito la
# emite el mismo módulo, pero su documento se arma con otras líneas (las
# acreditadas): ver Deuda técnica.
TIPOS_IMPRIMIBLES = ("boleta", "factura")

TITULOS = {
    "boleta": "BOLETA DE VENTA ELECTRÓNICA",
    "factura": "FACTURA ELECTRÓNICA",
}

AVISOS_EMISION = {
    "pendiente": "PENDIENTE DE ENVÍO A SUNAT",
    "error": "PENDIENTE DE ENVÍO A SUNAT",
    "rechazado": "RECHAZADO POR SUNAT - NO VÁLIDO",
}

PIE_POR_DEFECTO = ["Representación impresa del comprobante electrónico."]


def encabezado(session: Session, sucursal_id: uuid.UUID | None) -> dict:
    """Quién emite, tal como sale en la cabecera del rollo.

    Lo configurable vive en `marca.skins["ticket"]` —columna que ya existía
    para el branding del PDV— y no en una tabla nueva: son dos campos por
    marca (el logo y las líneas de cortesía del pie), y una tabla propia
    para eso sería un CRUD y una migración por cada línea de texto.
    """
    repo = ComprobanteRepo(session)
    sucursal = repo.sucursal(sucursal_id)
    if sucursal is None:
        return _encabezado_vacio()
    empresa = repo.empresa(sucursal.empresa_id)
    marca = repo.marca(sucursal.marca_id)
    config = ((marca.skins or {}).get("ticket") or {}) if marca else {}
    return {
        "marca": marca.nombre if marca else "",
        # Ruta servida por el frontend (`public/marcas/`). Es una ruta y no
        # un binario: el logo se cambia reemplazando el archivo, sin migrar
        # nada ni volver a subirlo por cada sucursal.
        "logo": config.get("logo"),
        "razon_social": empresa.razon_social if empresa else "",
        "ruc": empresa.ruc if empresa else "",
        "domicilio_fiscal": empresa.domicilio_fiscal if empresa else "",
        "contacto": empresa.contacto if empresa else None,
        "sucursal": sucursal.nombre,
        "direccion": sucursal.direccion,
        "pie": list(config.get("pie") or PIE_POR_DEFECTO),
    }


def _encabezado_vacio() -> dict:
    """Una venta sin sucursal resoluble no bloquea la impresión: el cuerpo
    del documento sigue siendo válido y el papel sale sin membrete."""
    return {
        "marca": "",
        "logo": None,
        "razon_social": "",
        "ruc": "",
        "domicilio_fiscal": "",
        "contacto": None,
        "sucursal": "",
        "direccion": "",
        "pie": list(PIE_POR_DEFECTO),
    }


def ticket_comprobante(session: Session, comprobante_id: uuid.UUID) -> dict:
    comprobante = ComprobanteRepo(session).get(comprobante_id)
    if comprobante is None:
        raise NoEncontrado("comprobante no encontrado")
    if comprobante.direccion != "emitido":
        raise Conflicto("solo se imprime un comprobante propio, no uno recibido")
    if comprobante.tipo not in TIPOS_IMPRIMIBLES:
        raise Conflicto(
            f"el tipo {comprobante.tipo} no tiene representación impresa propia"
        )

    documento = comprobantes.documento_de(session, comprobante)
    payload = factiliza.construir_payload(documento)

    fecha = comprobantes.fecha_emision(comprobante)
    igv = Decimal(str(payload["monto_Igv"]))
    total = Decimal(str(payload["monto_Imp_Venta"]))

    cadena = qr_sunat.cadena(
        ruc_emisor=documento.empresa_ruc,
        tipo_doc=documento.tipo_doc,
        serie=comprobante.serie,
        correlativo=comprobante.correlativo,
        igv=igv,
        total=total,
        fecha_emision=fecha.date(),
        tipo_doc_receptor=documento.cliente.tipo_doc,
        num_doc_receptor=documento.cliente.num_doc,
    )

    return {
        "comprobante_id": str(comprobante.id),
        "venta_id": str(comprobante.venta_id) if comprobante.venta_id else None,
        "encabezado": encabezado(session, _sucursal_de(session, comprobante)),
        "documento": {
            "tipo": comprobante.tipo,
            "titulo": TITULOS[comprobante.tipo],
            "serie": comprobante.serie,
            "correlativo": comprobante.correlativo,
            "serie_correlativo": f"{comprobante.serie}-{comprobante.correlativo:08d}",
            "fecha_emision": fecha.isoformat(),
            "grupo_cobro": comprobante.grupo_cobro,
            "estado_emision": comprobante.estado_emision,
            "aviso": AVISOS_EMISION.get(comprobante.estado_emision),
        },
        "receptor": {
            "tipo_doc": documento.cliente.tipo_doc,
            "num_doc": documento.cliente.num_doc,
            "nombre": documento.cliente.razon_social,
            "direccion": documento.cliente.direccion,
        },
        "items": [_item(linea) for linea in payload["detalle"]],
        "totales": {
            "gravadas": Decimal(str(payload["monto_Oper_Gravadas"])),
            "exoneradas": Decimal(str(payload["monto_Oper_Exoneradas"])),
            "igv": igv,
            "igv_porcentaje": (
                Decimal(0) if documento.exonerado_igv else settings.igv_porcentaje
            ),
            "total": total,
            "en_letras": payload["legend"][0]["legend_Value"],
        },
        "pie": {
            "qr_texto": cadena,
            # `data:` y no SVG en crudo: el ticket se pinta en el navegador y
            # un `<img src>` no puede ejecutar nada, un SVG inyectado sí.
            "qr_imagen": segno.make(cadena, error="m").svg_data_uri(
                scale=4, border=1, dark="#000000", light="#ffffff"
            ),
            "hash": comprobante.hash_proveedor,
        },
    }


def _sucursal_de(session: Session, comprobante: Comprobante) -> uuid.UUID | None:
    if comprobante.venta_id is None:
        return None
    venta = VentaRepo(session).get(comprobante.venta_id)
    return venta.sucursal_id if venta else None


def _item(linea: dict) -> dict:
    """Una línea del payload leída como la lee el cliente: precio con IGV e
    importe de la línea."""
    valor_venta = Decimal(str(linea["monto_Valor_Venta"]))
    igv = Decimal(str(linea["igv"]))
    return {
        "cantidad": Decimal(str(linea["cantidad"])),
        "descripcion": linea["descripcion"],
        "precio_unitario": Decimal(str(linea["monto_Precio_Unitario"])),
        "importe": valor_venta + igv,
    }
