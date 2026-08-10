"""Los destinos de un reporte existen de verdad (ADR-036).

Un reporte que enlaza a un endpoint que ya no está no falla: devuelve 404 y
vuelve a ser una línea de texto, que es exactamente el problema que estos
enlaces vinieron a resolver. Por eso el contrato se congela acá y no en la
pantalla: un rename de endpoint tiene que romper CI, no la operación.
"""

import uuid

import pytest

from src.core import destinos
from src.core.app import create_app
from src.core.reportes import catalogo as consultas
from src.modules.reports.domain import catalogo as emisiones
from tests.test_arquitectura import _rutas


def _rutas_montadas() -> set[str]:
    return {
        getattr(ruta, "path", "")
        for ruta in _rutas(create_app())
        if getattr(ruta, "path", "")
    }


@pytest.mark.parametrize(
    "tipo", sorted(destinos.DESTINOS), ids=lambda t: t
)
def test_todo_destino_apunta_a_un_endpoint_montado(tipo: str) -> None:
    """El `{id}` del mapa se traduce al `{nombre_del_param}` que FastAPI
    registró: la comparación es por forma de ruta, no por texto literal.

    Las rutas montadas se leen sin `PREFIJO_API` —el prefijo lo aplica
    `create_app()` al incluir el router—, que es la misma forma en que se
    guardan en `DESTINOS`.
    """
    ruta = destinos.DESTINOS[tipo].ruta
    montadas = {_normalizar(r) for r in _rutas_montadas()}
    assert _normalizar(ruta) in montadas, (
        f"`{tipo}` apunta a {ruta}, que no está montada en la app"
    )


def _normalizar(ruta: str) -> str:
    """`/inventory/lotes/{lote_id}` y `/inventory/lotes/{id}` son la misma
    ruta: el nombre del path param es interno del handler."""
    partes = [
        "{}" if p.startswith("{") and p.endswith("}") else p
        for p in ruta.split("/")
    ]
    return "/".join(partes)


@pytest.mark.parametrize(
    "emision",
    [e for e in emisiones.CATALOGO if e.referencia_tipo],
    ids=lambda e: e.codigo,
)
def test_toda_emision_con_referencia_tiene_destino(emision) -> None:
    """RN-REP-010. Una emisión que declara a qué apunta y no tiene destino
    deja al lector sin a dónde ir, que es el estado del que venimos."""
    assert emision.referencia_tipo in destinos.DESTINOS


@pytest.mark.parametrize(
    "reporte",
    [r for r in consultas.CATALOGO if any(c.enlace for c in r.columnas)],
    ids=lambda r: r.codigo,
)
def test_todo_enlace_del_tablero_tiene_destino(reporte) -> None:
    for columna in reporte.columnas:
        if columna.enlace:
            assert columna.enlace in destinos.DESTINOS


def test_el_permiso_del_destino_es_el_del_modulo_dueno() -> None:
    """Nunca un permiso de `reports` salvo cuando la entidad **es** de
    `reports` (el escalamiento): ser destinatario no da acceso al dato
    (RN-REP-002), y un juego de permisos propio sería una matriz paralela que
    se desincroniza."""
    propias = {"escalamiento"}
    for tipo, destino in destinos.DESTINOS.items():
        assert "." in destino.permiso
        if tipo not in propias:
            assert not destino.permiso.startswith("reports.")


def test_un_reporte_sin_referencia_no_tiene_url() -> None:
    assert destinos.url(None, uuid.uuid4()) is None
    assert destinos.url("venta", None) is None
    assert destinos.url("no_existe", uuid.uuid4()) is None


def test_la_url_lleva_el_prefijo_de_la_api() -> None:
    referencia = uuid.uuid4()
    assert destinos.url("venta", referencia) == f"/api/v1/sales/ventas/{referencia}"
