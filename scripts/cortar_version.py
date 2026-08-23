"""Junta los fragmentos de `changelog.d/` en una sección nueva de CHANGELOG.md.

Existe para que `CHANGELOG.md` deje de ser un punto de inserción compartido:
cada cambio escribe su propio archivo y el conflicto entre ramas paralelas
deja de ser posible. Ver `changelog.d/README.md`.

También escribe la versión en `pyproject.toml` y `frontend/package.json`. No
lo hacía, y para el 2026-08-09 el repo iba por `v0.4.0` con los dos archivos
declarando `0.1.0`: la versión vivía solo en el tag de git, así que cualquier
cosa que la leyera del proyecto —el paquete de demo, por ejemplo— mentía.

Uso: `python scripts/cortar_version.py 0.3.0 [--fecha 2026-08-09]`
"""

import argparse
import datetime
import os
import pathlib
import re
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CHANGELOG = RAIZ / "CHANGELOG.md"
FRAGMENTOS = RAIZ / "changelog.d"
PYPROJECT = RAIZ / "pyproject.toml"
PACKAGE_JSON = RAIZ / "frontend" / "package.json"

#: archivo -> patrón de la línea que declara la versión. El `count=1` de abajo
#: importa: `package.json` menciona versiones de dependencias más abajo.
_VERSION_EN = {
    PYPROJECT: re.compile(r'^(version = ")[^"]+(")', re.M),
    PACKAGE_JSON: re.compile(r'^(\s*"version":\s*")[^"]+(")', re.M),
}

#: Orden de Keep a Changelog. El prefijo del nombre del archivo decide la
#: sección, así que un tipo fuera de esta lista es un error de nombre.
TIPOS = ("added", "changed", "deprecated", "removed", "fixed", "security")

_ENCABEZADO = "## [Unreleased]"


def leer_fragmentos(directorio: pathlib.Path) -> dict[str, list[str]]:
    """Agrupa el contenido de los fragmentos por tipo, en orden de nombre."""
    por_tipo: dict[str, list[str]] = {}
    for archivo in sorted(directorio.glob("*.md")):
        if archivo.name == "README.md":
            continue
        tipo = archivo.name.split("-", 1)[0]
        if tipo not in TIPOS:
            raise SystemExit(
                f"{archivo.name}: '{tipo}' no es un tipo válido. "
                f"Usar uno de: {', '.join(TIPOS)}."
            )
        por_tipo.setdefault(tipo, []).append(archivo.read_text(encoding="utf-8").strip())
    return por_tipo


def armar_seccion(version: str, fecha: str, por_tipo: dict[str, list[str]]) -> str:
    partes = [f"## [{version}] - {fecha}", ""]
    for tipo in TIPOS:
        if tipo not in por_tipo:
            continue
        partes += [f"### {tipo.capitalize()}", ""]
        partes += ["\n\n".join(por_tipo[tipo]), ""]
    return "\n".join(partes)


def cortar(texto: str, seccion: str) -> str:
    """Inserta la sección nueva justo debajo del bloque `[Unreleased]`."""
    if _ENCABEZADO not in texto:
        raise SystemExit(f"No encontré '{_ENCABEZADO}' en CHANGELOG.md.")
    cabeza, _, cola = texto.partition(_ENCABEZADO)
    _, _, resto = cola.partition("\n## ")
    return f"{cabeza}{_ENCABEZADO}\n\nVer [`changelog.d/`](changelog.d/).\n\n{seccion}\n## {resto}"


def sellar_version(version: str) -> None:
    """Deja la versión escrita en los dos archivos que la declaran."""
    for archivo, patron in _VERSION_EN.items():
        texto = archivo.read_text(encoding="utf-8")
        nuevo, cambios = patron.subn(rf"\g<1>{version}\g<2>", texto, count=1)
        if not cambios:
            raise SystemExit(f"No encontré la línea de versión en {archivo.name}.")
        archivo.write_text(nuevo, encoding="utf-8", newline="")


def regenerar_openapi(version: str) -> None:
    """El contrato exportado lleva la versión adentro (`info.version`).

    Sin este paso, cortar una versión deja `docs/architecture/openapi.json`
    diciendo la anterior y **el job `backend` del CI falla**: hay un test que
    compara el archivo commiteado contra una exportación fresca. Pasó en el
    corte de 0.7.0, y no se ve venir en local — `settings.app_version` sale de
    la metadata del **paquete instalado**, que en un entorno editable sigue
    diciendo la versión vieja hasta que alguien reinstala. En el CI la
    instalación es limpia, así que ahí sí cambia.

    Por eso se fuerza por `APP_VERSION` en vez de confiar en la metadata: lo
    que vale es la versión que se acaba de sellar, no la que quedó instalada.
    """
    entorno = {**os.environ, "APP_VERSION": version}
    resultado = subprocess.run(
        [sys.executable, "-m", "src.core.openapi_export"],
        cwd=RAIZ,
        env=entorno,
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0:
        raise SystemExit(
            "No se pudo regenerar docs/architecture/openapi.json:\n"
            + (resultado.stderr or resultado.stdout)
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("version", help="versión SemVer sin la 'v', ej. 0.3.0")
    p.add_argument("--fecha", default=datetime.date.today().isoformat())
    p.add_argument(
        "--sin-openapi",
        action="store_true",
        help="no regenerar el contrato (solo para la autocomprobación)",
    )
    args = p.parse_args(argv)

    por_tipo = leer_fragmentos(FRAGMENTOS)
    if not por_tipo:
        raise SystemExit("No hay fragmentos en changelog.d/: nada que cortar.")

    texto = CHANGELOG.read_text(encoding="utf-8")
    CHANGELOG.write_text(
        cortar(texto, armar_seccion(args.version, args.fecha, por_tipo)),
        encoding="utf-8",
        newline="",
    )
    for archivo in FRAGMENTOS.glob("*.md"):
        if archivo.name != "README.md":
            archivo.unlink()
    sellar_version(args.version)
    if not args.sin_openapi:
        regenerar_openapi(args.version)

    total = sum(len(v) for v in por_tipo.values())
    print(f"{args.version}: {total} fragmentos en {len(por_tipo)} secciones.")
    print(f"Versión escrita en {PYPROJECT.name} y frontend/{PACKAGE_JSON.name}.")
    if not args.sin_openapi:
        print("Contrato OpenAPI regenerado con la versión nueva.")
    return 0


def _autocomprobacion() -> None:
    """Lo que puede romperse en silencio: dónde se inserta y qué se sella."""
    for archivo, patron in _VERSION_EN.items():
        texto = archivo.read_text(encoding="utf-8")
        nuevo, cambios = patron.subn(r"\g<1>9.9.9\g<2>", texto, count=1)
        assert cambios == 1, f"{archivo.name}: el patrón de versión ya no engancha"
        assert '"9.9.9"' in nuevo or "9.9.9" in nuevo, f"{archivo.name}: no reemplazó"

    antes = (
        "# Changelog\n\n## [Unreleased]\n\nVer [`changelog.d/`](changelog.d/).\n\n"
        "## [0.2.0] - 2026-08-08\n\n### Added\n\n- algo viejo\n"
    )
    nuevo = cortar(antes, armar_seccion("0.3.0", "2026-08-09", {"fixed": ["- algo nuevo"]}))
    assert nuevo.index("## [0.3.0]") < nuevo.index("## [0.2.0]"), "la nueva va arriba"
    assert "- algo viejo" in nuevo, "no se pierde lo anterior"
    assert "### Fixed\n\n- algo nuevo" in nuevo, "el tipo arma su encabezado"
    assert nuevo.count(_ENCABEZADO) == 1, "[Unreleased] queda una sola vez"
    print("autocomprobación ok")


if __name__ == "__main__":
    if "--autocomprobacion" in sys.argv:
        _autocomprobacion()
    else:
        raise SystemExit(main())
