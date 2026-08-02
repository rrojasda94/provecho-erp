"""Migración `b82d4c1f7a35`: los umbrales de `regla_aprobacion` pasan a
`parametro_empresa` como parámetros ya aprobados, y la tabla vieja se borra.

Corre el `upgrade()` real contra SQLite. `regla_aprobacion` ya no existe en
`Base.metadata` (el modelo se borró), así que se recrea a mano — que es
justamente el estado del que parte la migración.
"""

import importlib.util
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.users.infrastructure.models import Empresa, Usuario
from src.shared import aprobaciones
from src.shared.models import ParametroEmpresa

_CREAR_REGLA_APROBACION = """
CREATE TABLE regla_aprobacion (
    id CHAR(32) PRIMARY KEY,
    empresa_id CHAR(32) NOT NULL,
    modulo VARCHAR(50) NOT NULL,
    codigo VARCHAR(50) NOT NULL,
    umbral NUMERIC(12, 2) NOT NULL,
    permiso_requerido VARCHAR(100) NOT NULL,
    vigente BOOLEAN NOT NULL
)
"""


_RUTAS = {
    "b82d4c1f7a35": "alembic/versions/b82d4c1f7a35_retirar_regla_aprobacion_a_parametro_empresa.py",
    "c93e5a7b1d42": "alembic/versions/c93e5a7b1d42_divisa_decimales_por_udm_y_valor_display.py",
}


def _migracion(revision: str = "b82d4c1f7a35"):
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
    TestSession = sessionmaker(bind=e, autoflush=False, expire_on_commit=False)
    from src.seeders.seed import seed

    with TestSession() as s:
        seed(s)
        s.commit()
    with e.begin() as c:
        c.exec_driver_sql(_CREAR_REGLA_APROBACION)
    yield e, TestSession


def _sembrar_regla(engine, empresa_id, modulo, codigo, umbral, vigente=True):
    with engine.begin() as c:
        c.exec_driver_sql(
            "INSERT INTO regla_aprobacion VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, empresa_id.hex, modulo, codigo, umbral,
             "purchases.aprobar", vigente),
        )


def _correr_upgrade(engine):
    with engine.begin() as c:
        with Operations.context(MigrationContext.configure(c)):
            _migracion().upgrade()


def test_upgrade_copia_vigentes_y_borra_la_tabla(engine):
    e, TestSession = engine
    with TestSession() as s:
        empresa_id = s.scalar(select(Empresa.id))
        admin_id = s.scalar(select(Usuario.id).where(Usuario.username == "admin"))
    _sembrar_regla(e, empresa_id, "purchases", "oc_umbral", "10000.00")
    _sembrar_regla(e, empresa_id, "accounting", "pago_umbral", "500.00", vigente=False)

    _correr_upgrade(e)

    assert "regla_aprobacion" not in sa.inspect(e).get_table_names()
    with TestSession() as s:
        migrados = list(s.scalars(select(ParametroEmpresa)))
    # Solo la vigente: una regla dada de baja no revive como parámetro.
    assert [(p.modulo, p.codigo) for p in migrados] == [("purchases", "oc_umbral")]
    p = migrados[0]
    assert p.valor == {"monto": "10000.00"}
    assert p.estado == "vigente"
    assert p.propuesto_por_id == admin_id and p.resuelto_por_id == admin_id
    assert p.resuelto_en is not None


def test_upgrade_no_pisa_un_parametro_vigente_ya_cargado(engine):
    """Si alguien ya cargó el parámetro a mano, la migración no lo duplica —
    el índice único parcial explotaría."""
    e, TestSession = engine
    with TestSession() as s:
        empresa_id = s.scalar(select(Empresa.id))
        admin_id = s.scalar(select(Usuario.id).where(Usuario.username == "admin"))
        s.add(
            ParametroEmpresa(
                empresa_id=empresa_id,
                modulo="purchases",
                codigo="oc_umbral",
                valor={"monto": "7777.00"},
                estado="vigente",
                propuesto_por_id=admin_id,
            )
        )
        s.commit()
    _sembrar_regla(e, empresa_id, "purchases", "oc_umbral", "10000.00")

    _correr_upgrade(e)

    with TestSession() as s:
        vigentes = list(s.scalars(select(ParametroEmpresa)))
    assert len(vigentes) == 1
    assert vigentes[0].valor == {"monto": "7777.00"}


def test_upgrade_sin_reglas_solo_borra_la_tabla(engine):
    e, TestSession = engine
    _correr_upgrade(e)
    assert "regla_aprobacion" not in sa.inspect(e).get_table_names()
    with TestSession() as s:
        assert list(s.scalars(select(ParametroEmpresa))) == []


def test_c93_completa_la_divisa_del_umbral_migrado(engine):
    """`regla_aprobacion` nunca tuvo divisa, así que `b82` copia el monto
    sin ella. `c93` la completa con PEN (RN-PRC-004) para que ninguna fila
    quede incumpliendo RN-GER-010, y deja el display congelado."""
    e, TestSession = engine
    with TestSession() as s:
        empresa_id = s.scalar(select(Empresa.id))
    _sembrar_regla(e, empresa_id, "purchases", "oc_umbral", "10000.00")

    _correr_upgrade(e)
    with e.begin() as c:
        # `valor_display` ya lo creó Base.metadata; solo corre el backfill.
        with Operations.context(MigrationContext.configure(c)):
            _migracion("c93e5a7b1d42")._completar_divisa_de_montos_existentes()

    with TestSession() as s:
        migrado = s.scalar(select(ParametroEmpresa))
        assert migrado.valor == {"monto": "10000.00", "divisa": "PEN"}
        assert migrado.valor_display == "S/ 10000.00"
        assert aprobaciones.umbral_vigente(
            s, empresa_id, "purchases", "oc_umbral", default=Decimal("2000")
        ) == Decimal("10000.00")
