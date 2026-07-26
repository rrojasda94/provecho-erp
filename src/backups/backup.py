"""Backup de la base de datos: dump, verificación, purga y copia externa.

Un backup que nunca se restauró no es un backup — por eso `verificar` no es
un extra opcional del flujo, corre siempre (y, si hay una base desechable
configurada, restaura de verdad contra ella).

Uso:
    python -m src.backups.backup                 # dump + verificar + purgar + subir
    python -m src.backups.backup --solo-verificar backups/provecho-20260726.dump
    python -m src.backups.backup --restaurar backups/provecho-20260726.dump
"""

import argparse
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.engine import make_url

from src.config.settings import settings
from src.core.logging_config import configurar_logging
from src.core.sentry import iniciar_sentry, reportar

PREFIJO = "provecho-"
EXTENSION = ".dump"
# Un dump de Postgres en formato custom siempre arranca con esta firma.
FIRMA_DUMP_CUSTOM = b"PGDMP"
# Tablas que deben aparecer en el índice del dump: si el backup no las trae,
# no sirve por más que el archivo se lea bien.
TABLAS_CRITICAS = ("venta", "comprobante", "movimiento_inventario", "usuario")


class BackupError(RuntimeError):
    pass


def _dsn_libpq(url_sqlalchemy: str) -> tuple[list[str], dict[str, str]]:
    """Traduce el DSN de SQLAlchemy a flags de libpq.

    La contraseña viaja por entorno (`PGPASSWORD`), nunca en argv: `ps` la
    dejaría a la vista de cualquier usuario del servidor.
    """
    url = make_url(url_sqlalchemy)
    flags = ["-h", url.host or "localhost", "-p", str(url.port or 5432)]
    if url.username:
        flags += ["-U", url.username]
    entorno = {"PGPASSWORD": url.password} if url.password else {}
    return flags + ["-d", url.database or ""], entorno


def _correr(comando: list[str], entorno_extra: dict[str, str], que: str) -> str:
    entorno = {**os.environ, **entorno_extra}
    try:
        proceso = subprocess.run(  # noqa: S603 — comando fijo, sin shell
            comando, capture_output=True, text=True, env=entorno, check=False
        )
    except FileNotFoundError as e:
        raise BackupError(
            f"{comando[0]} no está instalado. Instalar postgresql-client "
            f"(la versión del cliente debe ser >= la del servidor)."
        ) from e
    if proceso.returncode != 0:
        raise BackupError(f"{que} falló: {proceso.stderr.strip()[:500]}")
    return proceso.stdout


def nombre_backup(momento: datetime | None = None) -> str:
    momento = momento or datetime.now(UTC)
    return f"{PREFIJO}{momento.strftime('%Y%m%d-%H%M%S')}{EXTENSION}"


def crear_backup(directorio: Path, database_url: str | None = None) -> Path:
    """Dump completo en formato custom (comprimido y restaurable selectivamente)."""
    directorio.mkdir(parents=True, exist_ok=True)
    destino = directorio / nombre_backup()
    flags, entorno = _dsn_libpq(database_url or settings.database_url)
    _correr(
        ["pg_dump", *flags, "--format=custom", "--no-owner", "--file", str(destino)],
        entorno,
        "pg_dump",
    )
    if not destino.exists() or destino.stat().st_size == 0:
        raise BackupError("pg_dump terminó bien pero no dejó archivo")
    return destino


def verificar_archivo(ruta: Path) -> dict:
    """Comprobación barata: el archivo es un dump legible y trae las tablas
    críticas. Detecta el caso frecuente (dump truncado por disco lleno)."""
    if not ruta.exists():
        raise BackupError(f"no existe {ruta}")
    with ruta.open("rb") as f:
        if f.read(len(FIRMA_DUMP_CUSTOM)) != FIRMA_DUMP_CUSTOM:
            raise BackupError(f"{ruta.name} no es un dump de Postgres")
    indice = _correr(["pg_restore", "--list", str(ruta)], {}, "pg_restore --list")
    faltantes = [t for t in TABLAS_CRITICAS if f" {t} " not in indice]
    if faltantes:
        raise BackupError(f"el dump no contiene: {', '.join(faltantes)}")
    return {"archivo": ruta.name, "bytes": ruta.stat().st_size, "tablas_ok": True}


def verificar_restaurando(ruta: Path, verify_url: str, produccion_url: str) -> dict:
    """Restaura el dump en una base DESECHABLE. Es la única prueba real de
    que el backup sirve.

    Rechaza apuntar a la misma base de producción: la restauración borra el
    esquema antes de escribir.
    """
    if not verify_url:
        raise BackupError("BACKUP_VERIFY_DATABASE_URL no configurada")
    if make_url(verify_url).database == make_url(produccion_url).database and make_url(
        verify_url
    ).host == make_url(produccion_url).host:
        raise BackupError(
            "la base de verificación es la misma que la de origen; "
            "restaurar ahí borraría los datos reales"
        )
    flags, entorno = _dsn_libpq(verify_url)
    _correr(
        ["pg_restore", *flags, "--clean", "--if-exists", "--no-owner", str(ruta)],
        entorno,
        "pg_restore",
    )
    filas = _correr(
        [
            "psql",
            *flags,
            "-t",
            "-A",
            "-c",
            "SELECT count(*) FROM usuario;",
        ],
        entorno,
        "psql",
    )
    return {"restaurado_en": make_url(verify_url).database, "usuarios": int(filas.strip())}


def backups_a_purgar(
    directorio: Path, retencion_dias: int, ahora: datetime | None = None
) -> list[Path]:
    """Archivos fuera de la retención. Nunca devuelve el más reciente: si
    todo quedó viejo (el cron llevaba semanas caído), borrarlo dejaría al
    ERP sin ninguna copia."""
    ahora = ahora or datetime.now(UTC)
    limite = ahora - timedelta(days=retencion_dias)
    archivos = sorted(
        directorio.glob(f"{PREFIJO}*{EXTENSION}"),
        key=lambda p: p.stat().st_mtime,
    )
    if not archivos:
        return []
    mas_reciente = archivos[-1]
    return [
        p
        for p in archivos[:-1]
        if datetime.fromtimestamp(p.stat().st_mtime, UTC) < limite and p != mas_reciente
    ]


def purgar(directorio: Path, retencion_dias: int) -> list[Path]:
    borrados = backups_a_purgar(directorio, retencion_dias)
    for ruta in borrados:
        ruta.unlink()
    return borrados


def copia_externa_configurada() -> bool:
    return bool(settings.s3_bucket and settings.s3_access_key and settings.s3_secret_key)


def subir_copia_externa(ruta: Path) -> str | None:
    """Copia fuera del servidor (S3 o compatible). Un incendio o un
    ransomware que se lleve el servidor se lleva también sus backups locales.

    `boto3` es dependencia opcional (`pip install -e ".[backups]"`) — se
    importa acá para no cargarla en la imagen de la API.
    """
    if not copia_externa_configurada():
        return None
    try:
        import boto3
    except ImportError as e:
        raise BackupError('falta boto3: pip install -e ".[backups]"') from e

    cliente = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint or None,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )
    clave = f"backups/{ruta.name}"
    cliente.upload_file(str(ruta), settings.s3_bucket, clave)
    return f"s3://{settings.s3_bucket}/{clave}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backup de la base de Provecho")
    parser.add_argument("--solo-verificar", metavar="ARCHIVO")
    parser.add_argument(
        "--restaurar",
        metavar="ARCHIVO",
        help="restaura en BACKUP_VERIFY_DATABASE_URL (base desechable)",
    )
    args = parser.parse_args(argv)
    configurar_logging()
    # Un backup que falla de noche no lo lee nadie: que llegue al reporte
    # de errores, no solo al log del cron.
    iniciar_sentry("backups")
    directorio = Path(settings.backup_dir)

    try:
        if args.solo_verificar:
            print(verificar_archivo(Path(args.solo_verificar)))
            return 0
        if args.restaurar:
            print(
                verificar_restaurando(
                    Path(args.restaurar),
                    settings.backup_verify_database_url,
                    settings.database_url,
                )
            )
            return 0

        ruta = crear_backup(directorio)
        print(f"backup creado: {ruta} ({ruta.stat().st_size:,} bytes)")
        print(f"verificado: {verificar_archivo(ruta)}")

        if settings.backup_verify_database_url:
            prueba = verificar_restaurando(
                ruta, settings.backup_verify_database_url, settings.database_url
            )
            print(f"restauración probada: {prueba}")
        else:
            print(
                "AVISO: sin BACKUP_VERIFY_DATABASE_URL no se probó la "
                "restauración — solo se validó el archivo"
            )

        destino_externo = subir_copia_externa(ruta)
        if destino_externo:
            print(f"copia externa: {destino_externo}")
        else:
            print("AVISO: sin credenciales S3 la única copia vive en este servidor")

        purgados = purgar(directorio, settings.backup_retencion_dias)
        print(f"purgados {len(purgados)} backups de más de {settings.backup_retencion_dias} días")
    except BackupError as e:
        reportar(e)
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 — el cron necesita el reporte
        reportar(e)
        print(f"ERROR inesperado: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
