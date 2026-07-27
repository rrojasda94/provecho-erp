"""Contrato OpenAPI: el archivo commiteado refleja la API real, y su forma
mínima (tags descritos, sin duplicados) no se degrada en silencio."""

import json
from pathlib import Path

from src.core.app import TAGS_METADATA, create_app
from src.core.openapi_export import DESTINO, escribir, generar


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


def test_el_archivo_commiteado_esta_al_dia() -> None:
    """Red flag temprana en local: si esto falla, `ci.yml` también va a
    fallar. Corre `python -m src.core.openapi_export` y commiteá el diff."""
    if not DESTINO.exists():
        return  # entorno sin checkout completo (p.ej. worktree parcial)
    vigente = json.dumps(generar(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    commiteado = DESTINO.read_text(encoding="utf-8")
    assert vigente == commiteado, (
        "docs/architecture/openapi.json desactualizado — correr "
        "`python -m src.core.openapi_export` y commitear el resultado"
    )


def test_health_router_usa_el_tag_core() -> None:
    """El tag `core` documentado debe corresponder a los endpoints reales
    de salud, no quedar huérfano en la metadata."""
    esquema = generar()
    tags_de_health = esquema["paths"]["/health"]["get"]["tags"]
    assert tags_de_health == ["core"]


def test_create_app_no_se_rompe_sin_configuracion_extra() -> None:
    assert create_app().openapi()["openapi"]  # versión de la spec, ej. "3.1.0"
