"""La versión del paquete no puede atrasarse respecto del CHANGELOG.

El caso que motiva el archivo: `pyproject.toml` se quedó en **0.1.0** mientras
el CHANGELOG y los tags iban por **0.5.0**. La versión se tecleaba tres veces
al cortar un release —argumento del script, mensaje de commit y tag— y no
aterrizaba en ningún archivo salvo `CHANGELOG.md`; nadie la escribía en
`pyproject.toml`, así que nada la movía nunca.

No era cosmético: de ahí salen el `release` con el que GlitchTip agrupa los
errores y la versión que publica `/docs`. Cuatro releases de errores cayeron
etiquetados como "0.1.0", que es justo lo que vuelve inservible el "esto
apareció en la versión X".
"""

import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[1]


def _version_de_pyproject() -> str:
    texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    encontrado = re.search(r'^version = "([^"]+)"', texto, re.MULTILINE)
    assert encontrado, "pyproject.toml no tiene línea 'version = ...'"
    return encontrado.group(1)


def _ultima_version_publicada() -> str:
    """La primera sección con número del CHANGELOG. `[Unreleased]` no cuenta:
    no es una versión, es el buzón de los fragmentos todavía sin cortar."""
    texto = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")
    encontrado = re.search(r"^## \[(\d+\.\d+\.\d+)\]", texto, re.MULTILINE)
    assert encontrado, "el CHANGELOG no tiene ninguna sección de versión"
    return encontrado.group(1)


def test_pyproject_va_a_la_par_del_changelog():
    assert _version_de_pyproject() == _ultima_version_publicada(), (
        "pyproject.toml quedó atrás del CHANGELOG. Al cortar una versión, "
        "`scripts/cortar_version.py` mueve las dos — si esto falla, se editó "
        "el CHANGELOG a mano."
    )


def test_settings_reporta_la_version_del_checkout():
    r"""`app_version` alimenta el `release` de GlitchTip, la versión de `/docs`
    y la que queda escrita en `docs/architecture/openapi.json`.

    Se lee del `pyproject.toml` del checkout y no de la metadata del paquete
    instalado, porque en un `pip install -e .` esa metadata se escribe una
    sola vez: el código queda en vivo y la versión no. Una máquina de
    desarrollo terminaba reportando la versión de la rama que estaba abierta
    el día que se instaló —se vio un venv en 0.6.0 con el repo en 0.9.1— y
    regenerar el contrato ahí lo ensuciaba con esa versión ajena, haciendo
    fallar el `git diff --exit-code` del CI sin que nadie tocara un endpoint.

    Un `assert` de igualdad y no de formato: `\d+\.\d+\.\d+` daba verde con
    los cuatro releases de diferencia, que es lo que había que detectar.
    """
    from src.config.settings import settings

    assert settings.app_version == _version_de_pyproject()
