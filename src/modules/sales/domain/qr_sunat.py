"""Cadena del código QR que SUNAT exige en la representación impresa.

La define la RS 097-2012/SUNAT (anexo de representación impresa): nueve
campos separados por `|` y un `|` final. No es texto libre ni un enlace —
quien fiscaliza escanea el QR y compara campo por campo contra el XML, así
que un separador de más o un monto con distinta cantidad de decimales
invalida el control aunque el papel se vea bien.

Vive en el dominio y no en `shared/integrations/factiliza` a propósito: esto
lo manda SUNAT, no el proveedor. Cambiar de proveedor no cambia esta cadena.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

_CENTIMOS = Decimal("0.01")


def _dos(valor: Decimal) -> str:
    return f"{Decimal(valor).quantize(_CENTIMOS, rounding=ROUND_HALF_UP):.2f}"


def cadena(
    *,
    ruc_emisor: str,
    tipo_doc: str,
    serie: str,
    correlativo: int,
    igv: Decimal,
    total: Decimal,
    fecha_emision: date,
    tipo_doc_receptor: str,
    num_doc_receptor: str,
) -> str:
    """Los nueve campos, en el orden del anexo, con `|` final.

    El correlativo va **sin** relleno de ceros: el XML lo declara así y el
    QR tiene que decir lo mismo que el XML.
    """
    campos = (
        ruc_emisor,
        tipo_doc,
        serie,
        str(correlativo),
        _dos(igv),
        _dos(total),
        fecha_emision.isoformat(),
        tipo_doc_receptor,
        num_doc_receptor,
    )
    return "|".join(campos) + "|"
