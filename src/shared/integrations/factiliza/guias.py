"""Traducción de una guía de remisión a la carga útil de Factiliza (GRE).

Aparte de `mapper.py` a propósito: la guía **no tiene aritmética
tributaria**. No lleva valor de venta, ni IGV, ni forma de pago — declara
qué bienes se mueven, desde dónde, hacia dónde y quién los lleva. Meterla
en el mismo archivo que la factura invitaba a reusar el cálculo de IGV
sobre un documento que no cobra nada.

Como el resto del adaptador, no importa el dominio de ningún módulo: recibe
dataclasses neutras y devuelve el JSON que espera la API.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

# Catálogo 01 — tipo de comprobante: guía de remisión remitente.
TIPO_DOC_GUIA_REMITENTE = "09"

# Catálogo 03 — unidad de medida. Solo se mapean las que el negocio usa; el
# catálogo de SUNAT tiene cientos y adivinar el resto sería peor que el
# fallback. Una unidad sin mapear sale como `NIU` (unidad), que es lo que
# SUNAT espera de un bien contable por piezas.
#
# El lugar correcto para esto es una columna `codigo_sunat` en
# `unidad_medida`, editable desde Catálogo (ver ROADMAP → Deuda técnica):
# mientras solo la guía lo necesite, una columna que alguien tiene que
# llenar a mano es más trabajo que este diccionario.
UNIDAD_SUNAT_POR_DEFECTO = "NIU"
UNIDADES_SUNAT = {
    "kilo": "KGM",
    "kilogramo": "KGM",
    "gramo": "GRM",
    "litro": "LTR",
    "mililitro": "MLT",
    "unidad": "NIU",
    "caja": "BX",
    "paquete": "PK",
    "bolsa": "BG",
    "botella": "BO",
    "docena": "DZN",
    "metro": "MTR",
}


def codigo_unidad(nombre_udm: str) -> str:
    """Código SUNAT de una unidad de medida por su nombre en el catálogo."""
    return UNIDADES_SUNAT.get((nombre_udm or "").strip().lower(), UNIDAD_SUNAT_POR_DEFECTO)


@dataclass(frozen=True)
class ItemGuia:
    codigo: str
    descripcion: str
    cantidad: Decimal
    unidad: str = UNIDAD_SUNAT_POR_DEFECTO


@dataclass(frozen=True)
class Guia:
    empresa_ruc: str
    serie: str
    correlativo: int
    fecha_emision: datetime
    fecha_inicio_traslado: date
    motivo_traslado: str
    modalidad_traslado: str
    peso_bruto_kg: Decimal
    receptor_ruc: str
    lugar_origen: str
    lugar_destino: str
    chofer_nombres: str
    chofer_apellidos: str
    chofer_num_doc: str
    chofer_licencia: str
    vehiculo_placa: str
    items: list[ItemGuia]
    unidad_peso: str = "KGM"


def construir_payload_guia(guia: Guia) -> dict:
    """Arma el cuerpo de `POST /despatch/send`."""
    return {
        "tipo_Doc": TIPO_DOC_GUIA_REMITENTE,
        "serie": guia.serie,
        "correlativo": str(guia.correlativo),
        "fecha_Emision": guia.fecha_emision.isoformat(),
        "empresa_Ruc": guia.empresa_ruc,
        "destinatario_Tipo_Doc": "6",
        "destinatario_Num_Doc": guia.receptor_ruc,
        "cod_Traslado": guia.motivo_traslado,
        "modalidad_Traslado": guia.modalidad_traslado,
        "fecha_Traslado": guia.fecha_inicio_traslado.isoformat(),
        "peso_Total": float(guia.peso_bruto_kg),
        "und_Peso_Total": guia.unidad_peso,
        "partida_Direccion": guia.lugar_origen,
        "llegada_Direccion": guia.lugar_destino,
        "chofer_Tipo_Doc": "1",
        "chofer_Num_Doc": guia.chofer_num_doc,
        "chofer_Nombres": guia.chofer_nombres,
        "chofer_Apellidos": guia.chofer_apellidos,
        "chofer_Licencia": guia.chofer_licencia,
        "vehiculo_Placa": guia.vehiculo_placa,
        "detalle": [
            {
                "unidad": item.unidad,
                "cantidad": float(item.cantidad),
                "cod_Producto": item.codigo,
                "descripcion": item.descripcion,
            }
            for item in guia.items
        ],
    }
