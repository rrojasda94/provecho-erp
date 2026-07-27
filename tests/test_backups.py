"""Backups: purga por retención, verificación del dump y guardarraíles.

No corre pg_dump de verdad — se sustituye `subprocess.run`.
"""

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.backups import backup
from src.backups.backup import BackupError

_DSN_PROD = "postgresql+psycopg://provecho:secreto@db.prod.supabase.co:5432/postgres"


def _archivo(directorio: Path, nombre: str, dias_atras: float) -> Path:
    ruta = directorio / nombre
    ruta.write_bytes(backup.FIRMA_DUMP_CUSTOM + b"contenido")
    momento = (datetime.now(UTC) - timedelta(days=dias_atras)).timestamp()
    import os

    os.utime(ruta, (momento, momento))
    return ruta


# --- Purga por retención -----------------------------------------------------
def test_purga_borra_solo_lo_viejo(tmp_path: Path) -> None:
    viejo = _archivo(tmp_path, "provecho-20260101-030000.dump", dias_atras=40)
    reciente = _archivo(tmp_path, "provecho-20260725-030000.dump", dias_atras=1)
    hoy = _archivo(tmp_path, "provecho-20260726-030000.dump", dias_atras=0)

    borrados = backup.purgar(tmp_path, retencion_dias=30)

    assert borrados == [viejo]
    assert reciente.exists() and hoy.exists()


def test_purga_nunca_borra_el_backup_mas_reciente(tmp_path: Path) -> None:
    """El cron estuvo caído meses: todo quedó fuera de retención. Borrarlo
    todo dejaría al ERP sin ninguna copia."""
    _archivo(tmp_path, "provecho-20250101-030000.dump", dias_atras=400)
    ultimo = _archivo(tmp_path, "provecho-20250301-030000.dump", dias_atras=300)

    backup.purgar(tmp_path, retencion_dias=30)

    assert ultimo.exists()
    assert list(tmp_path.glob("provecho-*.dump")) == [ultimo]


def test_purga_ignora_archivos_ajenos(tmp_path: Path) -> None:
    ajeno = tmp_path / "otra-cosa.dump"
    ajeno.write_bytes(b"x")
    import os

    viejo_ts = (datetime.now(UTC) - timedelta(days=400)).timestamp()
    os.utime(ajeno, (viejo_ts, viejo_ts))
    _archivo(tmp_path, "provecho-20260726-030000.dump", dias_atras=0)

    assert backup.purgar(tmp_path, retencion_dias=30) == []
    assert ajeno.exists()


def test_purga_en_directorio_vacio_no_falla(tmp_path: Path) -> None:
    assert backup.purgar(tmp_path, retencion_dias=30) == []


# --- Verificación del archivo ------------------------------------------------
def _indice_falso(tablas: tuple[str, ...]) -> str:
    return "\n".join(f"123; 1259 16xxx TABLE public {t} provecho" for t in tablas)


def _stub_run(salida: str = "", returncode: int = 0, stderr: str = ""):
    def _run(comando, **kwargs):
        return subprocess.CompletedProcess(comando, returncode, salida, stderr)

    return _run


def test_verificar_acepta_un_dump_con_las_tablas_criticas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta = _archivo(tmp_path, "provecho-20260726-030000.dump", dias_atras=0)
    monkeypatch.setattr(
        subprocess, "run", _stub_run(_indice_falso(backup.TABLAS_CRITICAS))
    )
    assert backup.verificar_archivo(ruta)["tablas_ok"] is True


def test_verificar_rechaza_un_dump_sin_las_tablas_criticas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un dump que se lee bien pero vino vacío es el peor caso: parece sano."""
    ruta = _archivo(tmp_path, "provecho-20260726-030000.dump", dias_atras=0)
    monkeypatch.setattr(subprocess, "run", _stub_run(_indice_falso(("usuario",))))
    with pytest.raises(BackupError, match="no contiene"):
        backup.verificar_archivo(ruta)


def test_verificar_rechaza_un_archivo_truncado(tmp_path: Path) -> None:
    ruta = tmp_path / "provecho-20260726-030000.dump"
    ruta.write_bytes(b"basura")
    with pytest.raises(BackupError, match="no es un dump"):
        backup.verificar_archivo(ruta)


def test_verificar_rechaza_archivo_inexistente(tmp_path: Path) -> None:
    with pytest.raises(BackupError, match="no existe"):
        backup.verificar_archivo(tmp_path / "no-esta.dump")


# --- Guardarraíl de la restauración de prueba --------------------------------
def test_restaurar_sobre_la_base_de_origen_esta_prohibido() -> None:
    """`pg_restore --clean` borra el esquema antes de escribir: apuntar a
    producción destruiría los datos que el backup debía proteger."""
    with pytest.raises(BackupError, match="borraría los datos reales"):
        backup.verificar_restaurando(Path("x.dump"), _DSN_PROD, _DSN_PROD)


def test_restaurar_sin_base_de_prueba_configurada_falla_claro() -> None:
    with pytest.raises(BackupError, match="BACKUP_VERIFY_DATABASE_URL"):
        backup.verificar_restaurando(Path("x.dump"), "", _DSN_PROD)


def test_restaurar_en_otra_base_si_procede(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _stub_run("7\n"))
    verify = "postgresql+psycopg://provecho:x@localhost:5433/provecho_verify"
    assert backup.verificar_restaurando(Path("x.dump"), verify, _DSN_PROD) == {
        "restaurado_en": "provecho_verify",
        "usuarios": 7,
    }


# --- Contraseña fuera de argv ------------------------------------------------
def test_la_contrasena_viaja_por_entorno_no_por_argv() -> None:
    """`ps` muestra argv a todo usuario del servidor."""
    flags, entorno = backup._dsn_libpq(_DSN_PROD)
    assert "secreto" not in " ".join(flags)
    assert entorno["PGPASSWORD"] == "secreto"
    assert flags[:4] == ["-h", "db.prod.supabase.co", "-p", "5432"]


def test_pg_dump_ausente_da_un_error_accionable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _explota(*a, **k):
        raise FileNotFoundError("pg_dump")

    monkeypatch.setattr(subprocess, "run", _explota)
    with pytest.raises(BackupError, match="postgresql-client"):
        backup.crear_backup(tmp_path, _DSN_PROD)


def test_dump_vacio_se_reporta_como_fallo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pg_dump puede salir con código 0 y no escribir nada (disco lleno)."""
    monkeypatch.setattr(subprocess, "run", _stub_run())
    with pytest.raises(BackupError, match="no dejó archivo"):
        backup.crear_backup(tmp_path, _DSN_PROD)


def test_comando_pg_dump_exacto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fija los flags: el dump real no se ejecuta en CI (no hay Postgres),
    así que al menos el comando queda bajo prueba."""
    capturado = {}

    def _run(comando, **kwargs):
        capturado["argv"] = comando
        capturado["env"] = kwargs.get("env", {})
        Path(comando[comando.index("--file") + 1]).write_bytes(
            backup.FIRMA_DUMP_CUSTOM + b"x"
        )
        return subprocess.CompletedProcess(comando, 0, "", "")

    monkeypatch.setattr(subprocess, "run", _run)
    ruta = backup.crear_backup(tmp_path, _DSN_PROD)

    assert capturado["argv"][:9] == [
        "pg_dump",
        "-h",
        "db.prod.supabase.co",
        "-p",
        "5432",
        "-U",
        "provecho",
        "-d",
        "postgres",
    ]
    assert "--format=custom" in capturado["argv"]
    assert "--no-owner" in capturado["argv"]
    assert capturado["env"]["PGPASSWORD"] == "secreto"
    assert ruta.parent == tmp_path


def test_nombre_de_backup_es_ordenable_por_fecha() -> None:
    momento = datetime(2026, 7, 26, 3, 0, 0, tzinfo=UTC)
    assert backup.nombre_backup(momento) == "provecho-20260726-030000.dump"


def test_sin_credenciales_no_hay_copia_externa(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.config import settings as modulo_settings

    monkeypatch.setattr(modulo_settings.settings, "s3_bucket", "")
    assert backup.copia_externa_configurada() is False
    assert backup.subir_copia_externa(Path("x.dump")) is None
