"""La migración de ADR-069, corrida de verdad contra SQLite.

Mismo patrón que `test_migracion_escalamiento.py`: `Base.metadata` ya crea el
esquema NUEVO (sin `trabajador.usuario_id`, con `uq_usuario_persona_viva`),
así que la migración se ejercita al revés — `downgrade` primero para volver
al esquema viejo, `upgrade` después para probar el camino real del CI.

El índice parcial en sí y el `DROP COLUMN` con FK solo se ejercitan de
verdad contra Postgres: eso lo cubre el job `migraciones` del CI. Lo que se
prueba acá es la lógica de backfill y las dos verificaciones que abortan
antes de dejar que Postgres reviente en la violación del índice.
"""

import importlib.util
import uuid

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.users.infrastructure.models import Empresa, Grupo, Persona, Usuario

_RUTA = (
    "alembic/versions/d3f8a2c1e947_la_cuenta_se_liga_al_trabajador_por_la_persona.py"
)


def _migracion():
    spec = importlib.util.spec_from_file_location("d3f8a2c1e947", _RUTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_la_cadena_de_revisiones_esta_encadenada() -> None:
    migracion = _migracion()
    assert migracion.down_revision == "c4d17b93e0af"


@pytest.fixture()
def engine():
    e = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(e)
    return e


def _operaciones(conexion):
    return Operations(MigrationContext.configure(conexion))


def _empresa_y_persona(conexion, nombres="Ana"):
    """Vía ORM y no SQL crudo: `empresa`/`persona`/`usuario` no cambian de
    forma con esta migración, y sus columnas obligatorias no importan acá —
    lo único que le interesa al test es `grupo_id`/`empresa_id`/`persona_id`."""
    s = Session(bind=conexion)
    grupo = s.scalar(sa.select(Grupo))
    if grupo is None:
        grupo = Grupo(nombre="Grupo")
        s.add(grupo)
        s.flush()
    empresa = Empresa(
        grupo_id=grupo.id,
        razon_social="Empresa",
        ruc=f"{uuid.uuid4().int % 10**11:011d}",
        domicilio_fiscal="Av. Test 1",
        tipo="operativa",
    )
    persona = Persona(
        nombres=nombres,
        apellidos="Torres",
        tipo_documento="dni",
        numero_documento=str(uuid.uuid4().int)[:8],
    )
    s.add_all([empresa, persona])
    s.flush()
    s.commit()
    return empresa.id, persona.id


def _usuario(conexion, persona_id=None):
    s = Session(bind=conexion)
    usuario_id = uuid.uuid4()
    usuario = Usuario(
        id=usuario_id,
        username=f"u{usuario_id.hex[:8]}",
        pin_hash="x",
        tipo="humano",
        persona_id=persona_id,
    )
    s.add(usuario)
    s.flush()
    s.commit()
    return usuario_id


def _trabajador(conexion, empresa_id, persona_id, usuario_id=None):
    trabajador_id = uuid.uuid4()
    conexion.execute(
        text(
            "INSERT INTO trabajador (id, empresa_id, persona_id, usuario_id, "
            "cargo, area, tipo_vinculo, fecha_ingreso, tiene_poderes, "
            "registra_asistencia, estado, created_at, updated_at) "
            "VALUES (:id, :empresa_id, :persona_id, :usuario_id, 'Cocinero', "
            "'Cocina', 'planilla', '2026-01-01', 0, 1, 'activo', "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {
            "id": trabajador_id.hex,
            "empresa_id": empresa_id.hex,
            "persona_id": persona_id.hex,
            "usuario_id": usuario_id.hex if usuario_id else None,
        },
    )
    return trabajador_id


def _al_esquema_viejo(conexion):
    """`Base.metadata` ya creó el esquema nuevo: baja primero para tener
    `trabajador.usuario_id` de vuelta y poder sembrar el estado de antes."""
    op = _operaciones(conexion)
    migracion = _migracion()
    migracion.op = op
    migracion.downgrade()
    return op, migracion


def test_el_backfill_mueve_el_vinculo_de_trabajador_a_usuario(engine) -> None:
    with engine.begin() as conexion:
        op, migracion = _al_esquema_viejo(conexion)
        empresa_id, persona_id = _empresa_y_persona(conexion)
        usuario_id = _usuario(conexion)  # sin persona_id todavía
        _trabajador(conexion, empresa_id, persona_id, usuario_id)

        migracion.upgrade()

        persona_vinculada = conexion.execute(
            text("SELECT persona_id FROM usuario WHERE id = :id"),
            {"id": usuario_id.hex},
        ).scalar()
        assert persona_vinculada == persona_id.hex

        columnas = {c["name"] for c in sa.inspect(conexion).get_columns("trabajador")}
        assert "usuario_id" not in columnas

        indices = {i["name"] for i in sa.inspect(conexion).get_indexes("usuario")}
        assert "uq_usuario_persona_viva" in indices


def test_el_backfill_no_pisa_una_persona_ya_vinculada(engine) -> None:
    """La cuenta ya estaba vinculada a otra persona por Usuarios (el camino
    que sí funcionaba): el backfill no la toca."""
    with engine.begin() as conexion:
        op, migracion = _al_esquema_viejo(conexion)
        empresa_id, persona_trabajador = _empresa_y_persona(conexion, nombres="Ana")
        _, persona_ya_vinculada = _empresa_y_persona(conexion, nombres="Beto")
        usuario_id = _usuario(conexion, persona_id=persona_ya_vinculada)
        _trabajador(conexion, empresa_id, persona_trabajador, usuario_id)

        migracion.upgrade()

        persona_final = conexion.execute(
            text("SELECT persona_id FROM usuario WHERE id = :id"),
            {"id": usuario_id.hex},
        ).scalar()
        assert persona_final == persona_ya_vinculada.hex


def test_aborta_si_una_persona_ya_tiene_dos_cuentas_vivas(engine) -> None:
    with engine.begin() as conexion:
        op, migracion = _al_esquema_viejo(conexion)
        _, persona_id = _empresa_y_persona(conexion)
        _usuario(conexion, persona_id=persona_id)
        _usuario(conexion, persona_id=persona_id)

        with pytest.raises(RuntimeError, match=str(persona_id)):
            migracion.upgrade()


def test_aborta_si_los_trabajadores_de_una_persona_apuntan_a_cuentas_distintas(
    engine,
) -> None:
    with engine.begin() as conexion:
        op, migracion = _al_esquema_viejo(conexion)
        empresa_id, persona_id = _empresa_y_persona(conexion)
        cuenta_1 = _usuario(conexion)
        cuenta_2 = _usuario(conexion)
        _trabajador(conexion, empresa_id, persona_id, cuenta_1)
        _trabajador(conexion, empresa_id, persona_id, cuenta_2)

        with pytest.raises(RuntimeError, match=str(persona_id)):
            migracion.upgrade()


def test_recontratacion_no_aborta_dos_trabajadores_una_cuenta(engine) -> None:
    """El caso legítimo: dos filas `trabajador` de una recontratación
    apuntando a LA MISMA cuenta no es el conflicto que el chequeo busca."""
    with engine.begin() as conexion:
        op, migracion = _al_esquema_viejo(conexion)
        empresa_id, persona_id = _empresa_y_persona(conexion)
        cuenta = _usuario(conexion)
        _trabajador(conexion, empresa_id, persona_id, cuenta)
        _trabajador(conexion, empresa_id, persona_id, cuenta)

        migracion.upgrade()  # no debe lanzar

        persona_vinculada = conexion.execute(
            text("SELECT persona_id FROM usuario WHERE id = :id"), {"id": cuenta.hex}
        ).scalar()
        assert persona_vinculada == persona_id.hex


def test_el_downgrade_repuebla_trabajador_usuario_id(engine) -> None:
    with engine.begin() as conexion:
        op, migracion = _al_esquema_viejo(conexion)
        empresa_id, persona_id = _empresa_y_persona(conexion)
        usuario_id = _usuario(conexion)
        trabajador_id = _trabajador(conexion, empresa_id, persona_id, usuario_id)
        migracion.upgrade()

        # Simula un vínculo hecho DESPUÉS del upgrade, ya en el esquema
        # nuevo: un downgrade real no puede perderlo.
        migracion.downgrade()
        columnas = {c["name"] for c in sa.inspect(conexion).get_columns("trabajador")}
        assert "usuario_id" in columnas
        repoblado = conexion.execute(
            text("SELECT usuario_id FROM trabajador WHERE id = :id"),
            {"id": trabajador_id.hex},
        ).scalar()
        assert repoblado == usuario_id.hex
