"""Semáforo del KDS: cuánto puede esperar un pedido antes de preocupar.

Los umbrales y colores los fija Gerencia por empresa (ADR-014 Addendum), con
el mismo mecanismo que la tarifa del delivery. Lo que se prueba acá es lo que
pasa cuando ese mecanismo devuelve algo raro: la pantalla de cocina no puede
quedarse sin colores porque alguien aprobó un `#zzz`.
"""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401  (puebla Base.metadata)
from src.core.database import Base
from src.modules.sales.application import kds_semaforo
from src.modules.sales.application.kds_semaforo import color_valido, semaforo_de, semilla
from src.modules.users.infrastructure.models import Empresa, Usuario
from src.shared.models import ParametroEmpresa


@pytest.fixture()
def empresa():
    """Empresa y usuario reales del seeder: `parametro_empresa` tiene FK a las
    dos y SQLite las valida en estos tests."""
    from src.seeders.seed import seed

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Sesion() as s:
        seed(s)
        s.commit()
        yield s, s.scalar(select(Empresa)).id, s.scalar(
            select(Usuario).where(Usuario.username == "admin")
        ).id


def _parametro(env, codigo: str, valor: dict, estado: str) -> None:
    """Se escribe la fila a mano y no por la API de Gerencia: lo que se prueba
    acá es cómo lee `sales` lo que hay en la tabla, no el flujo de aprobación
    —que ya tiene sus propios tests—."""
    session, empresa_id, admin_id = env
    session.add(
        ParametroEmpresa(
            empresa_id=empresa_id,
            modulo=kds_semaforo.MODULO,
            codigo=codigo,
            valor=valor,
            estado=estado,
            propuesto_por_id=admin_id,
        )
    )
    session.flush()


def _aprobar(env, codigo: str, valor: dict) -> None:
    _parametro(env, codigo, valor, "vigente")


def _proponer(env, codigo: str, valor: dict) -> None:
    _parametro(env, codigo, valor, "propuesto")


def _leer(env):
    """El semáforo resuelto de la empresa del fixture."""
    session, empresa_id, _ = env
    return semaforo_de(session, empresa_id)


def test_sin_nada_aprobado_manda_la_semilla(empresa):
    """El estado de una empresa el día que esto se despliega."""
    assert _leer(empresa) == semilla()


def test_lo_que_aprueba_gerencia_manda(empresa):
    _aprobar(empresa, kds_semaforo.CODIGO_MINUTOS_AMBAR, {"minutos": 3})
    _aprobar(empresa, kds_semaforo.CODIGO_MINUTOS_ROJO, {"minutos": 6})
    _aprobar(empresa, kds_semaforo.CODIGO_COLOR_ROJO, {"color": "#ff0000"})

    s = _leer(empresa)
    assert (s.minutos_ambar, s.minutos_rojo) == (3, 6)
    assert s.color_rojo == "#ff0000"
    # Lo que no se tocó sigue en la semilla.
    assert s.color_ambar == semilla().color_ambar


def test_una_propuesta_sin_aprobar_no_pinta_nada(empresa):
    """Todo el mecanismo de ADR-014: hasta que Gerencia no aprueba, el módulo
    no ve el valor."""
    _proponer(empresa, kds_semaforo.CODIGO_MINUTOS_AMBAR, {"minutos": 1})
    assert _leer(empresa).minutos_ambar == semilla().minutos_ambar


@pytest.mark.parametrize("basura", ["#zzz", "rojo", "#12345", "", None, 42])
def test_un_color_que_no_es_un_color_deja_el_de_fabrica(empresa, basura):
    """Un valor mal formado no puede dejar la cocina sin pantalla: el valor
    pasó por un formulario y por una aprobación, no por un compilador."""
    _aprobar(empresa, kds_semaforo.CODIGO_COLOR_AMBAR, {"color": basura})
    assert _leer(empresa).color_ambar == semilla().color_ambar


@pytest.mark.parametrize("minutos", [0, -5, 999, "ocho", None])
def test_un_umbral_fuera_de_rango_deja_el_de_fabrica(empresa, minutos):
    """Cero pintaría todo de rojo desde el primer segundo y apagaría el
    semáforo sin decirlo; cuatro horas no es un umbral, es un tecleo."""
    _aprobar(empresa, kds_semaforo.CODIGO_MINUTOS_AMBAR, {"minutos": minutos})
    assert _leer(empresa).minutos_ambar == semilla().minutos_ambar


def test_el_rojo_antes_que_el_ambar_deja_los_dos_de_fabrica(empresa):
    """Con el rojo antes que el ámbar el semáforo tendría dos niveles y no
    tres, y el ámbar sería invisible. Se cae a la semilla **completa**:
    corregir uno contra el otro dejaría una combinación que nadie aprobó."""
    _aprobar(empresa, kds_semaforo.CODIGO_MINUTOS_AMBAR, {"minutos": 20})
    _aprobar(empresa, kds_semaforo.CODIGO_MINUTOS_ROJO, {"minutos": 10})

    s = _leer(empresa)
    assert (s.minutos_ambar, s.minutos_rojo) == (
        semilla().minutos_ambar,
        semilla().minutos_rojo,
    )


def test_sin_empresa_no_se_rompe(empresa):
    """Superusuario sin empresa en el token: el parámetro es por empresa, así
    que no hay a quién preguntarle."""
    assert semaforo_de(empresa[0], None) == semilla()


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("#22c55e", True), ("#FFF000", True), ("#22c55", False), ("22c55e", False),
     ("#22c55g", False), ("", False), (None, False)],
)
def test_formato_de_color(valor, esperado):
    assert color_valido(valor) is esperado
