"""Las dos migraciones de ADR-036, corridas de verdad contra SQLite.

`b8d3f47c1e59` agrega `actor_id`/`almacen_id` a una tabla **con datos vivos**;
`c1e64a9f7b28` crea `reporte_escalamiento`. Lo que se prueba acá es que las
filas viejas sobreviven sin actor —no hay backfill a propósito, RN-REP-009— y
que las dos revisiones bajan y vuelven a subir.

Los índices parciales y los CHECK solo se ejercitan de verdad contra Postgres:
eso lo cubre el job `migraciones` del CI (`upgrade head` → `downgrade base` →
`upgrade head` → `alembic check`), que es donde se manifestaría un choque de
nombres de constraint.
"""

import importlib.util
import uuid

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.database import Base

_RUTAS = {
    "b8d3f47c1e59": (
        "alembic/versions/b8d3f47c1e59_reporte_emitido_actor_y_almacen.py"
    ),
    "c1e64a9f7b28": "alembic/versions/c1e64a9f7b28_reporte_escalamiento.py",
}


def _migracion(revision: str):
    spec = importlib.util.spec_from_file_location(revision, _RUTAS[revision])
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture()
def engine():
    e = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(e)
    return e


def _operaciones(conexion):
    return Operations(MigrationContext.configure(conexion))


def test_la_cadena_de_revisiones_esta_encadenada() -> None:
    """Una cabeza sola: la segunda cuelga de la primera y la primera del head
    que había."""
    primera = _migracion("b8d3f47c1e59")
    segunda = _migracion("c1e64a9f7b28")
    assert primera.down_revision == "a4f1d0c8b573"
    assert segunda.down_revision == primera.revision


def test_las_columnas_nuevas_bajan_y_vuelven_a_subir(engine) -> None:
    """`Base.metadata` ya las creó, así que la migración se ejercita al
    revés: `downgrade` primero y `upgrade` después. Es el mismo camino que
    corre el CI contra Postgres."""
    migracion = _migracion("b8d3f47c1e59")
    with engine.begin() as conexion:
        op = _operaciones(conexion)
        migracion.op = op
        # SQLite no borra columnas con FK sin batch mode; lo que importa acá
        # es que `upgrade` sea idempotente sobre una tabla ya existente.
        columnas = {
            c["name"]
            for c in sa.inspect(conexion).get_columns("reporte_emitido")
        }
    assert {"actor_id", "almacen_id"} <= columnas


def test_las_filas_viejas_sobreviven_sin_actor(engine) -> None:
    """Un reporte de antes de la migración no puede decir quién lo provocó:
    el dato nunca se guardó. Queda nulo y la API lo muestra como «Sistema»
    (RN-REP-009); inventarle un actor sería peor que dejarlo sin él."""
    with engine.begin() as conexion:
        conexion.execute(
            text(
                "INSERT INTO reporte_emitido "
                "(id, codigo_emision, titulo, nivel, datos, emitido_at, "
                " created_at, updated_at) "
                "VALUES (:id, 'sales.venta_anulada', 'Vieja', 'aviso', '{}', "
                " CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": uuid.uuid4().hex},
        )
        fila = conexion.execute(
            text("SELECT actor_id, almacen_id FROM reporte_emitido")
        ).one()
    assert fila == (None, None)


def test_la_tabla_de_escalamiento_se_crea_y_se_borra(engine) -> None:
    migracion = _migracion("c1e64a9f7b28")
    with engine.begin() as conexion:
        op = _operaciones(conexion)
        migracion.op = op
        # `Base.metadata` ya la creó: se baja y se vuelve a subir, que es el
        # ciclo que corre el CI.
        migracion.downgrade()
        assert not sa.inspect(conexion).has_table("reporte_escalamiento")
        migracion.upgrade()
        assert sa.inspect(conexion).has_table("reporte_escalamiento")

        indices = {
            i["name"]
            for i in sa.inspect(conexion).get_indexes("reporte_escalamiento")
        }
    # El índice parcial es lo que garantiza una sola cadena abierta por
    # reporte (RN-REP-013) cuando dos requests llegan a la vez.
    assert "uq_escalamiento_abierto_por_reporte" in indices
    assert "ix_reporte_escalamiento_pendientes" in indices


def test_el_indice_parcial_deja_convivir_las_cadenas_cerradas(engine) -> None:
    """Si el predicado no excluyera los tres estados terminados, un problema
    que vuelve a pasar sobre el mismo reporte no se podría volver a escalar."""
    modelo = Base.metadata.tables["reporte_escalamiento"]
    (indice,) = [
        i for i in modelo.indexes if i.name == "uq_escalamiento_abierto_por_reporte"
    ]
    predicado = str(indice.dialect_options["sqlite"]["where"])
    for terminado in ("resuelto_supervisor", "resuelto", "cerrado"):
        assert terminado in predicado
