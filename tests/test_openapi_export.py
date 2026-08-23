"""Contrato OpenAPI: el archivo commiteado refleja la API real, y su forma
mínima (tags descritos, sin duplicados) no se degrada en silencio."""

import json
import tomllib
from pathlib import Path

from src.core.app import TAGS_METADATA, create_app
from src.core.openapi_export import DESTINO, escribir, generar

PYPROJECT = Path("pyproject.toml")


def test_generar_devuelve_el_esquema_de_la_app_real() -> None:
    esquema = generar()
    assert esquema["info"]["title"] == "Provecho ERP"
    assert "/api/v1/sales/ventas" in esquema["paths"]
    assert "/health" in esquema["paths"]


def test_escribir_produce_json_valido_y_estable(tmp_path: Path) -> None:
    """Dos corridas seguidas deben producir bytes idénticos — si no, el
    check de CI (`git diff --exit-code`) marcaría diferencia en cada PR
    aunque nadie haya tocado un endpoint."""
    destino = tmp_path / "openapi.json"
    ruta1 = escribir(destino)
    contenido1 = ruta1.read_text(encoding="utf-8")
    escribir(destino)
    contenido2 = destino.read_text(encoding="utf-8")

    assert contenido1 == contenido2
    assert contenido1.endswith("\n")
    json.loads(contenido1)  # no lanza


def test_todos_los_tags_usados_tienen_descripcion() -> None:
    """Un tag sin metadata en TAGS_METADATA aparece en /docs sin
    explicación — señal de que alguien agregó un router y se olvidó."""
    esquema = generar()
    tags_documentados = {t["name"] for t in TAGS_METADATA}
    tags_en_rutas = {
        tag
        for ruta in esquema["paths"].values()
        for operacion in ruta.values()
        if isinstance(operacion, dict)
        for tag in operacion.get("tags", [])
    }
    assert tags_en_rutas <= tags_documentados, (
        f"Tags sin descripción en TAGS_METADATA: {tags_en_rutas - tags_documentados}"
    )


def test_no_hay_tags_duplicados_en_la_metadata() -> None:
    nombres = [t["name"] for t in TAGS_METADATA]
    assert len(nombres) == len(set(nombres))


def _sin_version(esquema: dict) -> dict:
    """El contrato sin `info.version`.

    La versión sale de la metadata del **paquete instalado**, y eso la vuelve
    inservible para detectar deriva del contrato: en un entorno editable dice
    la versión con la que se instaló hasta que alguien reinstala, y en el CI
    —instalación limpia— dice la de `pyproject.toml`. Comparar el archivo
    entero hacía que la misma rama pasara en local y fallara en CI sin que
    nadie hubiera tocado un endpoint. Pasó en el corte de 0.7.0.

    Que la versión del archivo sea la correcta lo comprueba
    `test_la_version_del_contrato_es_la_del_proyecto`, que la lee de
    `pyproject.toml` y por eso dice lo mismo en los dos entornos.
    """
    info = {k: v for k, v in esquema["info"].items() if k != "version"}
    return {**esquema, "info": info}


def test_el_archivo_commiteado_esta_al_dia() -> None:
    """Red flag temprana en local: si esto falla, `ci.yml` también va a
    fallar. Corre `python -m src.core.openapi_export` y commiteá el diff."""
    if not DESTINO.exists():
        return  # entorno sin checkout completo (p.ej. worktree parcial)
    commiteado = json.loads(DESTINO.read_text(encoding="utf-8"))
    assert _sin_version(generar()) == _sin_version(commiteado), (
        "docs/architecture/openapi.json desactualizado — correr "
        "`python -m src.core.openapi_export` y commitear el resultado"
    )


def test_la_version_del_contrato_es_la_del_proyecto() -> None:
    """Cortar una versión cambia `pyproject.toml`, y **el contrato la lleva
    adentro**: sin regenerarlo, el archivo commiteado sigue diciendo la
    anterior y el job `backend` falla con un diff de una línea.

    Pasó en el corte de 0.7.0. Ahora `cortar_version.py` lo regenera solo;
    esto es el guardarraíl para cuando alguien lo corte a mano.
    """
    if not DESTINO.exists():
        return
    declarada = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    commiteado = json.loads(DESTINO.read_text(encoding="utf-8"))
    assert commiteado["info"]["version"] == declarada, (
        f"openapi.json dice {commiteado['info']['version']} y pyproject.toml "
        f"dice {declarada} — regenerar con "
        f"`APP_VERSION={declarada} python -m src.core.openapi_export`"
    )


def test_health_router_usa_el_tag_core() -> None:
    """El tag `core` documentado debe corresponder a los endpoints reales
    de salud, no quedar huérfano en la metadata."""
    esquema = generar()
    tags_de_health = esquema["paths"]["/health"]["get"]["tags"]
    assert tags_de_health == ["core"]


def test_create_app_no_se_rompe_sin_configuracion_extra() -> None:
    assert create_app().openapi()["openapi"]  # versión de la spec, ej. "3.1.0"
