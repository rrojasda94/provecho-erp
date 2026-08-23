"""Junta los fragmentos de `changelog.d/` en una sección nueva de CHANGELOG.md.

Existe para que `CHANGELOG.md` deje de ser un punto de inserción compartido:
cada cambio escribe su propio archivo y el conflicto entre ramas paralelas
deja de ser posible. Ver `changelog.d/README.md`.

Uso: `python scripts/cortar_version.py 0.3.0 [--fecha 2026-08-09]`
"""

import argparse
import datetime
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CHANGELOG = RAIZ / "CHANGELOG.md"
FRAGMENTOS = RAIZ / "changelog.d"
PYPROJECT = RAIZ / "pyproject.toml"

#: La línea de `[project]`. Anclada al principio de línea a propósito:
#: `target-version` y las de las dependencias no empiezan con "version".
_VERSION_TOML = re.compile(r'^version = "[^"]+"', re.MULTILINE)

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


def subir_version(texto: str, version: str) -> str:
    """Mueve `version` de `[project]` en pyproject.toml.

    Sin esto el paquete se quedó en 0.1.0 mientras el CHANGELOG y los tags
    iban por 0.5.0: la versión se tecleaba tres veces —argumento, mensaje de
    commit y tag— y no aterrizaba en ningún archivo salvo el CHANGELOG. De ahí
    salen el `release` de GlitchTip y la versión de `/docs`, así que todos los
    errores de cuatro releases cayeron en el mismo balde.
    """
    nuevo, cambios = _VERSION_TOML.subn(f'version = "{version}"', texto, count=1)
    if cambios != 1:
        raise SystemExit("No encontré la línea 'version = ...' en pyproject.toml.")
    return nuevo


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("version", help="versión SemVer sin la 'v', ej. 0.3.0")
    p.add_argument("--fecha", default=datetime.date.today().isoformat())
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
    PYPROJECT.write_text(
        subir_version(PYPROJECT.read_text(encoding="utf-8"), args.version),
        encoding="utf-8",
        newline="",
    )
    for archivo in FRAGMENTOS.glob("*.md"):
        if archivo.name != "README.md":
            archivo.unlink()

    total = sum(len(v) for v in por_tipo.values())
    print(f"{args.version}: {total} fragmentos en {len(por_tipo)} secciones.")
    print("pyproject.toml actualizado. Reinstalar en dev: pip install -e '.[dev]'")
    return 0


def _autocomprobacion() -> None:
    """Lo único que puede romperse en silencio es dónde se inserta la sección."""
    antes = (
        "# Changelog\n\n## [Unreleased]\n\nVer [`changelog.d/`](changelog.d/).\n\n"
        "## [0.2.0] - 2026-08-08\n\n### Added\n\n- algo viejo\n"
    )
    nuevo = cortar(antes, armar_seccion("0.3.0", "2026-08-09", {"fixed": ["- algo nuevo"]}))
    assert nuevo.index("## [0.3.0]") < nuevo.index("## [0.2.0]"), "la nueva va arriba"
    assert "- algo viejo" in nuevo, "no se pierde lo anterior"
    assert "### Fixed\n\n- algo nuevo" in nuevo, "el tipo arma su encabezado"
    assert nuevo.count(_ENCABEZADO) == 1, "[Unreleased] queda una sola vez"

    toml = (
        '[project]\nname = "provecho"\nversion = "0.4.0"\n\n'
        '[tool.ruff]\ntarget-version = "py312"\n'
    )
    subido = subir_version(toml, "0.5.0")
    assert 'version = "0.5.0"' in subido, "mueve la versión de [project]"
    assert 'target-version = "py312"' in subido, "no toca target-version de ruff"
    print("autocomprobación ok")


if __name__ == "__main__":
    if "--autocomprobacion" in sys.argv:
        _autocomprobacion()
    else:
        raise SystemExit(main())
