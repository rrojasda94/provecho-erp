"""Consulta RUC/DNI contra Factiliza **de verdad**, saliendo a internet.

Es el único archivo del suite que toca la red, y por eso está marcado `red` y
excluido del `addopts`: `pytest` normal no lo corre ni en la máquina ni en el
CI. Se dispara a mano, **desde la raíz del repo** —que es donde vive el `.env`
con los tokens; desde otro directorio no los encuentra y todo queda `skipped`:

    pytest -m red

Por qué separado y no dentro de `test_factiliza_consulta.py`: cada llamada
gasta cuota de un proveedor **pago**, depende de que RENIEC/SUNAT estén
arriba, y el CI tendría que guardar el token como secreto. Un suite que se
pone rojo porque SUNAT se cayó deja de significar "el código está mal", que
es lo único que un suite sirve para decir.

**Solo consultas.** Acá no se emite nada: un `POST /invoice/send` contra
Factiliza genera un comprobante real ante SUNAT, y eso no es algo que dispare
una prueba. La emisión se valida con los dobles de
`test_facturacion_electronica.py`.

Los documentos son los mismos con los que se probó la integración el
2026-08-02 (ADR-005) — datos públicos de RENIEC/SUNAT.
"""

import pytest

from src.config.settings import settings
from src.shared.integrations.factiliza.client import FactilizaClient, FactilizaError

pytestmark = pytest.mark.red

DNI_DE_PRUEBA = "73632127"
RUC_DE_PRUEBA = "20610077782"


def _token_de_consulta() -> str:
    return settings.factiliza_consulta_documento_token or settings.factiliza_token


requiere_token = pytest.mark.skipif(
    not _token_de_consulta(),
    reason="sin FACTILIZA_CONSULTA_DOCUMENTO_TOKEN ni FACTILIZA_TOKEN en el entorno",
)


@requiere_token
def test_consultar_dni_contra_reniec():
    """El caso que estaba roto: con dos tokens distintos, esto respondía 401
    y el mostrador veía un 502 sin explicación."""
    r = FactilizaClient().consultar_dni(DNI_DE_PRUEBA)
    assert r.encontrado, f"RENIEC no devolvió el DNI {DNI_DE_PRUEBA}: {r.crudo}"
    assert r.nombres.strip()
    assert r.apellidos.strip()
    assert r.numero_documento == DNI_DE_PRUEBA


@requiere_token
def test_consultar_ruc_contra_sunat():
    r = FactilizaClient().consultar_ruc(RUC_DE_PRUEBA)
    assert r.encontrado, f"SUNAT no devolvió el RUC {RUC_DE_PRUEBA}: {r.crudo}"
    assert r.razon_social.strip()
    assert r.numero_documento == RUC_DE_PRUEBA


# El camino "no encontrado" se prueba con dobles en
# `test_factiliza_consulta.py`, no acá: dar con un DNI que de verdad no exista
# obliga a consultar documentos de desconocidos hasta que uno falle. El primer
# intento (`00000001`) devolvió a una persona real, con nombre y domicilio. No
# hay versión de esa prueba que valga los datos de un tercero.


@pytest.mark.skipif(
    not settings.factiliza_consulta_documento_token
    or settings.factiliza_consulta_documento_token == settings.factiliza_token,
    reason="hay un solo token: el plan cubre ambos productos con una credencial",
)
def test_el_token_de_emision_no_sirve_para_consultar():
    """La prueba de que separarlos no era teoría.

    Manda a propósito la credencial de emisión al host de consulta —lo que
    hacía el cliente antes— y verifica que Factiliza la rechaza. Si algún día
    esto empieza a pasar, significa que el proveedor unificó las credenciales
    y `FACTILIZA_CONSULTA_DOCUMENTO_TOKEN` dejó de hacer falta.
    """
    cliente = FactilizaClient(token_consulta=settings.factiliza_token)
    try:
        r = cliente.consultar_dni(DNI_DE_PRUEBA)
    except FactilizaError:
        return  # 5xx del proveedor ante la credencial equivocada: también es rechazo
    assert not r.encontrado, (
        "el token de emisión SÍ consultó documentos — Factiliza unificó los "
        "productos y este archivo hay que revisarlo"
    )
