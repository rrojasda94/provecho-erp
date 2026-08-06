"""Deriva de esquema: lo que los modelos declaran vs. lo que la base tiene.

Existe por un fallo real (2026-08-04): `alembic_version` marcaba una
revisión posterior a la que crea `decision_gerencial`, pero la tabla no
estaba. Alembic decía "al día" y el endpoint respondía 500. Nada en el
sistema lo notaba hasta que alguien abría esa pantalla.

Dos preguntas distintas, porque fallan distinto:

- **¿Falta alguna tabla del modelo?** Es el chequeo que importa: contesta
  por el estado real de la base, no por lo que el marcador dice. Atrapa la
  migración marcada y no corrida, la aplicada a medias y la base restaurada
  de un backup viejo.
- **¿La revisión coincide con la cabeza del repo?** Contesta por el
  marcador. Atrapa el despliegue al que le falta correr `alembic upgrade`,
  incluso cuando todas las tablas ya existen (una migración que solo agrega
  columnas o índices no se nota en la lista de tablas).

Se compara **solo la existencia de tablas**, no columnas ni tipos: es el
80% del daño con el 5% del código, y una comparación columna a columna
contra `Base.metadata` genera falsos positivos con cada detalle de dialecto.
Ver ROADMAP → Deuda técnica si algún día hace falta más fino.
"""

import logging
import pathlib
import re
from dataclasses import dataclass, field

from sqlalchemy import Engine, inspect, text

log = logging.getLogger("provecho.app")

_VERSIONES = pathlib.Path(__file__).resolve().parent.parent.parent / "alembic" / "versions"
_RE_REVISION = re.compile(r"^revision(?::\s*str)?\s*=\s*[\"']([^\"']+)", re.M)
_RE_DOWN = re.compile(r"^down_revision(?::\s*[^=]+)?\s*=\s*[\"']([^\"']+)", re.M)


@dataclass(frozen=True)
class Diagnostico:
    tablas_faltantes: tuple[str, ...] = ()
    revision_bd: str | None = None
    revision_repo: str | None = None
    # Vacío si no se pudo leer el directorio de migraciones (imagen sin
    # `alembic/`, por ejemplo): en ese caso no se afirma nada de la revisión.
    alertas: tuple[str, ...] = field(default=())

    @property
    def revision_desalineada(self) -> bool:
        if self.revision_bd is None or self.revision_repo is None:
            return False
        return self.revision_bd != self.revision_repo

    @property
    def hay_deriva(self) -> bool:
        return bool(self.tablas_faltantes) or self.revision_desalineada

    def resumen(self) -> str:
        if not self.hay_deriva:
            return "esquema al día"
        partes = []
        if self.tablas_faltantes:
            partes.append(
                "faltan tablas que el modelo declara: "
                + ", ".join(self.tablas_faltantes)
            )
        if self.revision_desalineada:
            partes.append(
                f"la base está en la revisión {self.revision_bd} y el repo espera "
                f"{self.revision_repo} (falta correr `alembic upgrade head`)"
            )
        return "; ".join(partes)


def head_del_repo() -> str | None:
    """La revisión sin hijos: la que `alembic upgrade head` alcanzaría.

    Se lee del directorio de migraciones y no de la API de Alembic para no
    montar su `Config` (que necesita el .ini y una conexión) solo para
    responder una pregunta de archivos.
    """
    if not _VERSIONES.is_dir():
        return None
    revisiones: set[str] = set()
    padres: set[str] = set()
    for archivo in _VERSIONES.glob("*.py"):
        texto = archivo.read_text(encoding="utf-8")
        if m := _RE_REVISION.search(texto):
            revisiones.add(m.group(1))
        if m := _RE_DOWN.search(texto):
            padres.add(m.group(1))
    cabezas = revisiones - padres
    # Dos cabezas es una rama sin mergear: CI ya lo falla aparte, acá solo
    # se evita afirmar una revisión esperada que no existe.
    return cabezas.pop() if len(cabezas) == 1 else None


def _revision_de_la_base(engine: Engine) -> tuple[str | None, tuple[str, ...]]:
    try:
        with engine.connect() as conexion:
            resultado = conexion.execute(text("SELECT version_num FROM alembic_version"))
            filas = [f[0] for f in resultado]
    except Exception:  # noqa: BLE001 — tabla ausente, permisos, o base virgen
        return None, ("no se pudo leer alembic_version",)
    if len(filas) != 1:
        return None, (f"alembic_version tiene {len(filas)} filas",)
    return filas[0], ()


def diagnosticar(engine: Engine, metadata) -> Diagnostico:
    """Compara `metadata` (los modelos) contra la base de `engine`.

    Una base inalcanzable **no es deriva**: es no haber podido mirar. Se
    reporta como alerta y sin tablas faltantes, para no confundir "el
    esquema está incompleto" con "no se pudo comparar" — de eso avisa
    `/health/ready`, que es quien mide si la base responde.
    """
    try:
        existentes = set(inspect(engine).get_table_names())
    except Exception:  # noqa: BLE001 — base caída, credenciales, red
        return Diagnostico(
            revision_repo=head_del_repo(),
            alertas=("no se pudo conectar a la base: el esquema no se comparó",),
        )
    faltantes = tuple(sorted(set(metadata.tables) - existentes))
    revision_bd, alertas = _revision_de_la_base(engine)
    return Diagnostico(
        tablas_faltantes=faltantes,
        revision_bd=revision_bd,
        revision_repo=head_del_repo(),
        alertas=alertas,
    )


def verificar_al_arrancar(engine: Engine, metadata, *, estricto: bool) -> Diagnostico:
    """Chequeo de arranque. `estricto` (producción) **aborta**.

    Mismo criterio que la validación de configuración: un ERP que arranca
    contra un esquema incompleto atiende requests hasta que alguien toca la
    pantalla equivocada, y entonces el error aparece lejos de su causa. En
    desarrollo solo avisa: media migración a medio escribir es normal ahí.
    """
    diagnostico = diagnosticar(engine, metadata)
    for alerta in diagnostico.alertas:
        log.warning("Chequeo de esquema: %s", alerta)
    if not diagnostico.hay_deriva:
        return diagnostico
    mensaje = f"Deriva de esquema: {diagnostico.resumen()}"
    if estricto:
        raise RuntimeError(mensaje)
    log.warning(mensaje)
    return diagnostico


def main() -> int:
    """`python -m src.core.esquema` — 0 si el esquema está al día, 1 si no.

    Pensado para el job de migraciones de CI y para mirar un servidor a
    mano: `docker compose exec api python -m src.core.esquema`.
    """
    import src.core.models_registry  # noqa: F401  (puebla `Base.metadata`)
    from src.core.database import Base, engine

    diagnostico = diagnosticar(engine, Base.metadata)
    for alerta in diagnostico.alertas:
        print(f"aviso: {alerta}")
    print(diagnostico.resumen())
    return 1 if diagnostico.hay_deriva else 0


if __name__ == "__main__":
    raise SystemExit(main())
