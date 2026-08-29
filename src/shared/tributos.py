"""Régimen de IGV de una operación: el único lugar del ERP que lo decide.

Antes lo decidían dos sitios por su cuenta —`accounting` al armar el asiento y
`sales` al armar el comprobante electrónico— con la misma línea copiada
(`empresa.zona_tributaria == "amazonia_ley27037"`). Dos copias de una regla
tributaria es una que se desactualiza: el día que una empresa cambie de
régimen, los libros y lo que se declara a SUNAT dirían cosas distintas.

Es transversal y no de un módulo (mismo criterio que `shared.fechas`): el IGV
no le pertenece a contabilidad ni a ventas, las dos lo consultan.

**Tres niveles, de más fuerte a más débil:**

1. **La operación**, cuando alguien la marcó — la casilla del comprobante.
   Una compra a un proveedor de fuera de la región llega con IGV en la
   factura aunque la empresa venda exonerada, y quien tiene la factura en la
   mano es el que lo ve.
2. **El default de la empresa** (`empresa.config_fiscal["igv_por_defecto"]`),
   que se elige en Organización → Empresas.
3. **La zona tributaria**, si nadie eligió nada. Es el comportamiento
   histórico, así que una empresa que ya existía no cambia de régimen porque
   se haya desplegado esto.

La exoneración de Amazonía (Ley 27037, RN-IMP-001) depende de zona **y
actividad** —ver `docs/contabilidad/marco-legal-contabilidad.md`—, y por eso
el nivel 2 existe: la zona sola no alcanza para decidir.
"""

from decimal import Decimal
from typing import Protocol

from src.config.settings import settings

#: Clave de `empresa.config_fiscal` donde vive el default.
CLAVE_DEFECTO = "igv_por_defecto"
GRAVADO = "gravado"
EXONERADO = "exonerado"
OPCIONES_DEFECTO = (GRAVADO, EXONERADO)

ZONA_EXONERADA = "amazonia_ley27037"


class RegimenEmpresa(Protocol):
    """Lo único que hace falta saber de la empresa.

    Un `Protocol` y no `Empresa`: `shared` no importa el dominio de `users`
    (CLAUDE.md), y de paso las pruebas pueden pasar cualquier objeto con
    estos dos campos.
    """

    zona_tributaria: str
    config_fiscal: dict | None


def gravado(empresa: RegimenEmpresa, explicito: bool | None = None) -> bool:
    """¿Esta operación lleva IGV?"""
    if explicito is not None:
        return explicito
    elegido = (empresa.config_fiscal or {}).get(CLAVE_DEFECTO)
    if elegido in OPCIONES_DEFECTO:
        return elegido == GRAVADO
    return empresa.zona_tributaria != ZONA_EXONERADA


def tasa_igv(empresa: RegimenEmpresa, explicito: bool | None = None) -> Decimal:
    """Tasa en porcentaje (18, no 0.18) o cero si la operación va exonerada.

    La tasa vigente es global (`settings.igv_porcentaje`) y no por empresa:
    la cambia una norma, no una decisión del grupo.
    """
    return Decimal(settings.igv_porcentaje) if gravado(empresa, explicito) else Decimal(0)
