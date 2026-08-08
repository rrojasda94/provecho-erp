"""Lo que hasta ahora se vigilaba a ojo entre archivos que no se importan.

Tres coherencias que ningún test funcional puede romper, porque no pasan por
el código: el número de un ADR, su entrada en el índice de documentación y la
versión de Python que corre el suite frente a la que envía la imagen. Las
tres fallaron de verdad el 2026-08-08 y las tres se detectaron a mano,
después del merge.

La cadena de Alembic no está acá porque el job `backend` ya falla si hay más
de una cabeza (ver `.github/workflows/ci.yml`).
"""

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ADRS = RAIZ / "docs" / "architecture" / "adr"
INDICE = RAIZ / "docs" / "00_PROJECT.md"
DOCKERFILE = RAIZ / "Dockerfile"
CI = RAIZ / ".github" / "workflows" / "ci.yml"

_NOMBRE_ADR = re.compile(r"^ADR-(\d{3})-[a-z0-9-]+\.md$")


def _numeros_de_adr() -> list[tuple[int, str]]:
    numerados = []
    for archivo in sorted(ADRS.glob("ADR-*.md")):
        coincidencia = _NOMBRE_ADR.match(archivo.name)
        assert coincidencia, (
            f"{archivo.name} no sigue el formato ADR-###-slug-en-minusculas.md"
        )
        numerados.append((int(coincidencia.group(1)), archivo.name))
    return numerados


def test_ningun_numero_de_adr_esta_repetido():
    """Tres ramas en paralelo pidieron el mismo número el 2026-08-08.

    Cada una eligió "el siguiente" contra el `main` que veía, y ninguna veía a
    las otras. Se resolvió renumerando dos veces a mano, después de mergear.
    El número lo sigue eligiendo una persona —no hay forma de reservarlo— así
    que lo único que se puede hacer es que el choque se vea en el PR y no
    después.
    """
    vistos: dict[int, str] = {}
    repetidos = []
    for numero, nombre in _numeros_de_adr():
        if numero in vistos:
            repetidos.append(f"ADR-{numero:03d}: {vistos[numero]} y {nombre}")
        vistos[numero] = nombre
    assert not repetidos, "Dos ADR con el mismo número:\n" + "\n".join(repetidos)


def test_la_numeracion_de_adr_no_tiene_huecos():
    """Un hueco casi siempre es un ADR renumerado a medias, no uno descartado.

    Si algún día se descarta uno de verdad, el archivo se queda con el estado
    `Descartado` escrito adentro: el número no se recicla.
    """
    numeros = [n for n, _ in _numeros_de_adr()]
    faltan = sorted(set(range(1, max(numeros) + 1)) - set(numeros))
    assert not faltan, f"Faltan los ADR: {faltan}"


def test_cada_adr_aparece_en_el_indice_de_documentacion():
    """`docs/00_PROJECT.md` es por dónde entra cualquiera —persona o agente—.

    Un ADR que no está listado ahí existe solo para quien ya sabía que
    existía.
    """
    indice = INDICE.read_text(encoding="utf-8")
    ausentes = [
        f"ADR-{numero:03d} ({nombre})"
        for numero, nombre in _numeros_de_adr()
        if f"{numero:03d} " not in indice and f"{numero} " not in indice
    ]
    assert not ausentes, "ADR sin entrada en docs/00_PROJECT.md:\n" + "\n".join(ausentes)


def test_el_python_del_ci_es_el_que_envia_la_imagen():
    """El PR #49 subió la imagen a 3.14 y dejó los cuatro jobs en 3.12.

    El job `imagen` solo comprueba que el contenedor construya y conteste
    `/health`: una dependencia incompatible con el intérprete nuevo habría
    llegado a producción con `main` en verde, porque `pytest` nunca lo
    ejecutó.
    """
    base = re.search(r"^FROM python:(\d+\.\d+)", DOCKERFILE.read_text(encoding="utf-8"), re.M)
    assert base, "No encontré el `FROM python:X.Y` del Dockerfile"
    imagen = base.group(1)

    jobs = re.findall(r'python-version:\s*"(\d+\.\d+)"', CI.read_text(encoding="utf-8"))
    assert jobs, "No encontré ningún `python-version:` en ci.yml"

    distintos = sorted(set(jobs) - {imagen})
    assert not distintos, (
        f"La imagen corre Python {imagen} y el CI prueba con {distintos}. "
        "Al subir el Dockerfile hay que subir los `python-version:` de ci.yml."
    )


@pytest.mark.parametrize("archivo", [INDICE, DOCKERFILE, CI])
def test_los_archivos_que_este_test_vigila_existen(archivo):
    """Si alguno se mueve, este test tiene que fallar en vez de no probar nada."""
    assert archivo.is_file(), f"{archivo.relative_to(RAIZ)} ya no está donde este test lo busca"
