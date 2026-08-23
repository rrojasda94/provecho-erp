"""Arma el paquete de demo portable: el ERP entero en un ZIP, sin internet.

Construye las dos imágenes de la demo, las exporta junto con Postgres y Redis,
y las empaqueta con `docker-compose.demo.yml` y los `.bat` que usa quien
prueba. El resultado queda en `ZIP_<versión>/provecho-demo-<versión>.zip`, una
carpeta por versión para que la que ya repartiste no se pise con la nueva.

Se ejecuta acá, no en el CI: el artefacto pesa ~1 GB, se reparte a mano y se
arma cuando hace falta, no en cada push.

Uso:
    python scripts/empaquetar_demo.py [--sin-construir]
"""

import argparse
import datetime
import pathlib
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
COMPOSE = RAIZ / "docker-compose.demo.yml"
DEMO = RAIZ / "scripts" / "demo"

#: Imágenes que el compose de la demo construye desde este repo:
#: etiqueta -> (contexto de build, Dockerfile, etapa).
IMAGENES_PROPIAS = {
    "provecho-demo-api:latest": (RAIZ, RAIZ / "Dockerfile", None),
    "provecho-demo-web:latest": (RAIZ / "frontend", RAIZ / "frontend" / "Dockerfile", "runtime"),
}

#: Imágenes de terceros. Van al tar igual: la PC del tester puede no tener
#: internet, y aunque lo tenga, bajarlas es la mitad de la espera del
#: primer arranque.
IMAGENES_BASE = ("postgres:16-alpine", "redis:7-alpine")

#: Todo lo que se exporta. `tests/test_repo_coherencia.py` comprueba que sea
#: exactamente lo que `docker-compose.demo.yml` nombra: agregar un servicio
#: allá sin tocar acá produciría un ZIP al que le falta una imagen, y el
#: tester solo vería una pantalla que no carga.
IMAGENES = tuple(IMAGENES_PROPIAS) + IMAGENES_BASE

#: Lo que ve el tester al descomprimir, además de `imagenes.tar`.
ARCHIVOS = ("INICIAR.bat", "APAGAR.bat", "REINICIAR-DEMO.bat", "LEEME.md")


def version() -> str:
    with (RAIZ / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def commit() -> str:
    """Commit exacto del que salió el paquete.

    La versión sola no alcanza: un ZIP se puede armar desde un árbol que no es
    el del tag (así salió el primero, cuatro commits detrás de `v0.4.0`). Sin
    esto, un tester que reporta un error no puede decir contra qué probó.
    """
    try:
        salida = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "desconocido"
    return salida.stdout.strip()


def imagenes_del_compose(texto: str) -> set[str]:
    """Etiquetas que declara `docker-compose.demo.yml`, sin depender de PyYAML."""
    return set(re.findall(r"^\s+image:\s*(\S+)\s*$", texto, re.M))


def _docker(*argumentos: str) -> None:
    print(f"  $ docker {' '.join(argumentos)}")
    subprocess.run(["docker", *argumentos], check=True)


def construir() -> None:
    for etiqueta, (contexto, dockerfile, etapa) in IMAGENES_PROPIAS.items():
        objetivo = ["--target", etapa] if etapa else []
        _docker(
            "build",
            "-t",
            etiqueta,
            "-f",
            str(dockerfile),
            *objetivo,
            str(contexto),
        )
    for etiqueta in IMAGENES_BASE:
        _docker("pull", etiqueta)


def empaquetar(destino: pathlib.Path, tar: pathlib.Path, version: str) -> None:
    raiz_interna = destino.stem
    sello = (
        "Provecho ERP - demo portable\r\n"
        f"Version: {version}\r\n"
        f"Commit:  {commit()}\r\n"
        f"Armado:  {datetime.date.today().isoformat()}\r\n"
        "\r\nSi reportas un problema, copia estas cuatro lineas.\r\n"
    )
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zip_:
        zip_.write(COMPOSE, f"{raiz_interna}/{COMPOSE.name}")
        zip_.writestr(f"{raiz_interna}/VERSION.txt", sello)
        for nombre in ARCHIVOS:
            zip_.write(DEMO / nombre, f"{raiz_interna}/{nombre}")
        # El tar es el 99% del peso; se comprime al final para que un fallo
        # copiando los archivos livianos se vea antes de esperar diez minutos.
        print("  Comprimiendo las imágenes (tarda varios minutos)...")
        zip_.write(tar, f"{raiz_interna}/{tar.name}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--sin-construir",
        action="store_true",
        help="reusa las imágenes que ya están en Docker (no las reconstruye)",
    )
    args = p.parse_args(argv)

    faltantes = imagenes_del_compose(COMPOSE.read_text(encoding="utf-8")) - set(IMAGENES)
    if faltantes:
        raise SystemExit(
            f"{COMPOSE.name} usa imágenes que este script no exporta: "
            f"{', '.join(sorted(faltantes))}. Agregarlas a IMAGENES_PROPIAS o IMAGENES_BASE."
        )

    if shutil.which("docker") is None:
        raise SystemExit("No encontré `docker` en el PATH.")

    v = version()
    carpeta = RAIZ / f"ZIP_{v}"
    carpeta.mkdir(exist_ok=True)
    tar = carpeta / "imagenes.tar"
    destino = carpeta / f"provecho-demo-{v}.zip"

    if not args.sin_construir:
        print(f"Construyendo las imágenes de la demo {v}...")
        construir()

    print("Exportando las imágenes...")
    _docker("save", "-o", str(tar), *IMAGENES)

    print(f"Armando {destino.relative_to(RAIZ)}...")
    empaquetar(destino, tar, v)
    tar.unlink()

    print(f"\nListo: {destino.relative_to(RAIZ)} ({destino.stat().st_size / 1024**2:.0f} MB)")
    print(f"Versión {v}, commit {commit()}.")
    print("Probarlo en frío: descomprimir en otra carpeta y doble clic en INICIAR.bat.")
    return 0


def _autocomprobacion() -> None:
    """Lo único con lógica propia acá es leer las imágenes del compose."""
    ejemplo = "services:\n  db:\n    image: postgres:16-alpine\n    restart: unless-stopped\n"
    assert imagenes_del_compose(ejemplo) == {"postgres:16-alpine"}, "lee la etiqueta"
    assert imagenes_del_compose("# image: comentada\n") == set(), "ignora comentarios"
    assert imagenes_del_compose(COMPOSE.read_text(encoding="utf-8")) <= set(IMAGENES), (
        "el compose de la demo nombra una imagen que no se exporta"
    )
    print("autocomprobación ok")


if __name__ == "__main__":
    if "--autocomprobacion" in sys.argv:
        _autocomprobacion()
    else:
        raise SystemExit(main())
