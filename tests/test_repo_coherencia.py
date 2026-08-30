"""Lo que hasta ahora se vigilaba a ojo entre archivos que no se importan.

Coherencias que ningún test funcional puede romper, porque no pasan por el
código: el número de un ADR, su entrada en el índice de documentación, las
versiones de Python y Node que corre el CI frente a las que envían las
imágenes, y las imágenes que el paquete de demo exporta frente a las que su
compose usa. Las tres primeras fallaron de verdad el 2026-08-08 y las tres se
detectaron a mano, después del merge.

La cadena de Alembic no está acá porque el job `backend` ya falla si hay más
de una cabeza (ver `.github/workflows/ci.yml`).
"""

import json
import pathlib
import re
import tomllib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = RAIZ / "pyproject.toml"
PACKAGE_JSON = RAIZ / "frontend" / "package.json"
ADRS = RAIZ / "docs" / "architecture" / "adr"
INDICE = RAIZ / "docs" / "00_PROJECT.md"
DOCKERFILE = RAIZ / "Dockerfile"
DOCKERFILE_WEB = RAIZ / "frontend" / "Dockerfile"
COMPOSE_DEMO = RAIZ / "docker-compose.demo.yml"
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


def test_el_node_del_ci_es_el_que_envia_la_imagen_del_frontend():
    """Mismo riesgo que con Python, en el otro lenguaje.

    El job `frontend` es el único que ejecuta `next build`: si la imagen se
    construye con otro Node, lo que se reparte en la demo es un build que
    nadie probó.
    """
    base = re.search(r"^FROM node:(\d+)", DOCKERFILE_WEB.read_text(encoding="utf-8"), re.M)
    assert base, "No encontré el `FROM node:X` del Dockerfile del frontend"

    jobs = re.findall(r'node-version:\s*"(\d+)"', CI.read_text(encoding="utf-8"))
    assert jobs, "No encontré ningún `node-version:` en ci.yml"

    distintos = sorted(set(jobs) - {base.group(1)})
    assert not distintos, (
        f"La imagen del frontend corre Node {base.group(1)} y el CI prueba con {distintos}."
    )


def test_el_paquete_de_demo_exporta_todas_las_imagenes_que_usa():
    """El ZIP y el compose de la demo no se importan entre sí, pero dependen.

    `docker-compose.demo.yml` no tiene `build:` —en la PC de quien prueba no
    hay código fuente—, así que un servicio nuevo con una imagen que el
    empaquetador no exporta produce un ZIP incompleto. Ahí no falla nada
    visible: el tester abre el navegador y ve una pantalla que no carga.
    """
    from scripts.empaquetar_demo import IMAGENES, imagenes_del_compose

    usadas = imagenes_del_compose(COMPOSE_DEMO.read_text(encoding="utf-8"))
    faltan = sorted(usadas - set(IMAGENES))
    assert not faltan, (
        f"docker-compose.demo.yml usa {faltan} y scripts/empaquetar_demo.py no las exporta."
    )

    sobran = sorted(set(IMAGENES) - usadas)
    assert not sobran, (
        f"scripts/empaquetar_demo.py exporta {sobran}, que ya nadie usa en el compose de la demo."
    )


def test_backend_y_frontend_declaran_la_misma_version():
    """La versión se escribe en dos archivos y nadie la leía de un solo lado.

    Hasta el 2026-08-09 `cortar_version.py` solo tocaba `CHANGELOG.md`: el repo
    iba por `v0.4.0` y los dos archivos seguían diciendo `0.1.0`, así que la
    versión vivía únicamente en el tag de git. Lo notó el paquete de demo, que
    nombra el ZIP con lo que dice `pyproject.toml` y salió etiquetado con una
    versión de hacía un mes.
    """
    with PYPROJECT.open("rb") as f:
        backend = tomllib.load(f)["project"]["version"]
    frontend = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["version"]
    assert backend == frontend, (
        f"pyproject.toml dice {backend} y frontend/package.json dice {frontend}. "
        "Las escribe `scripts/cortar_version.py` al cortar la versión."
    )


@pytest.mark.parametrize(
    "archivo", [INDICE, DOCKERFILE, DOCKERFILE_WEB, COMPOSE_DEMO, CI, PYPROJECT, PACKAGE_JSON]
)
def test_los_archivos_que_este_test_vigila_existen(archivo):
    """Si alguno se mueve, este test tiene que fallar en vez de no probar nada."""
    assert archivo.is_file(), f"{archivo.relative_to(RAIZ)} ya no está donde este test lo busca"


def test_las_descripciones_de_permiso_entran_en_su_columna():
    """`permiso.descripcion` es VARCHAR(255) y **Postgres lo hace cumplir**.

    SQLite no valida el largo, así que una descripción de más pasa toda la
    suite y revienta recién al sembrar contra la base real — con el seeder
    entero abortado y un `StringDataRightTruncation` que no dice qué permiso
    fue. Pasó con `users.resetear_pin` (260 caracteres, 2026-08-13).

    El tope se lee del modelo y no se escribe acá: si la columna crece,
    esta prueba acompaña sola.
    """
    from src.modules.users.infrastructure.models import Permiso
    from src.seeders.seed import PERMISOS

    tope = Permiso.__table__.c.descripcion.type.length
    largos = [
        f"{codigo}: {len(desc)} > {tope}"
        for codigo, desc in PERMISOS
        if desc and len(desc) > tope
    ]
    assert not largos, "descripciones de permiso que no entran:\n" + "\n".join(largos)


def test_la_imagen_lleva_lo_que_se_corre_dentro_del_contenedor() -> None:
    """`scripts/odoo/README.md` manda correr el cargador **adentro** del
    contenedor:

        docker compose exec api python -m scripts.odoo.cargar_catalogo ...

    Si el Dockerfile no copia `scripts/odoo`, ese comando falla con
    `No module named 'scripts'`. Pasó al cargar el catálogo en staging el
    2026-08-23: la documentación decía una cosa y la imagen tenía otra, y no
    hay forma de enterarse sin desplegar.

    Se comprueba lo que la imagen **tiene**, no lo que le falta: el resto de
    `scripts/` se queda afuera a propósito.
    """
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    readme = (RAIZ / "scripts" / "odoo" / "README.md").read_text(encoding="utf-8")
    if "docker compose" not in readme:
        return  # el README dejó de mandar correrlo adentro
    assert re.search(r"^COPY\s+scripts/odoo\s", dockerfile, re.M), (
        "scripts/odoo/README.md manda correr el cargador dentro del "
        "contenedor, pero el Dockerfile no copia `scripts/odoo`: el comando "
        "documentado falla con `No module named 'scripts'`"
    )



def test_los_motivos_de_descuento_del_pdv_son_los_que_la_api_acepta():
    """El PDV los ofrece como chips y la API los valida contra un conjunto
    cerrado: si las dos listas se separan, el cajero elige un motivo que el
    servidor rechaza con un 409 en el momento de firmar.

    `cupon` queda fuera del PDV a propósito: ese motivo lo pone el canje del
    cupón, no una persona eligiendo de una lista.
    """
    from src.modules.sales.domain.rules import MOTIVO_CUPON, MOTIVOS_DESCUENTO

    fuente = (RAIZ / "frontend/app/pdv/tipos.ts").read_text(encoding="utf-8")
    bloque = re.search(
        r"export const MOTIVOS_DESCUENTO = \[(.*?)\] as const;", fuente, re.S
    )
    assert bloque, "No encontré MOTIVOS_DESCUENTO en frontend/app/pdv/tipos.ts"
    del_pdv = set(re.findall(r'\["([a-z_]+)",', bloque.group(1)))

    assert del_pdv == MOTIVOS_DESCUENTO - {MOTIVO_CUPON}, (
        "los motivos de descuento del PDV y los de la API no coinciden: "
        f"PDV={sorted(del_pdv)} API={sorted(MOTIVOS_DESCUENTO - {MOTIVO_CUPON})}"
    )


def test_los_estados_del_filtro_de_la_jornada_son_los_del_enum_de_venta():
    """La pantalla `/ventas` filtra por `estado` y el backend lo valida contra
    `estado_venta`: si las dos listas se separan, el filtro no falla — devuelve
    cero filas, o esconde un estado entero.

    Pasó de verdad (auditoría del 2026-08-20, hallazgo 1): el desplegable
    ofrecía `entregada` —que es estado de ítem del KDS, no de venta— y no
    ofrecía `facturada`, que es donde termina casi todo lo cobrado.
    """
    from src.modules.sales.domain.rules import ESTADOS_VENTA

    fuente = (RAIZ / "frontend/app/(app)/ventas/jornada-cliente.tsx").read_text(
        encoding="utf-8"
    )
    bloque = re.search(r"const ESTADOS = \[(.*?)\];", fuente, re.S)
    assert bloque, "No encontré ESTADOS en frontend/app/(app)/ventas/jornada-cliente.tsx"
    de_la_pantalla = set(re.findall(r'"([a-z_]+)"', bloque.group(1)))

    assert de_la_pantalla == set(ESTADOS_VENTA), (
        "los estados del filtro de la jornada y los de la API no coinciden: "
        f"pantalla={sorted(de_la_pantalla)} API={sorted(ESTADOS_VENTA)}"
    )
