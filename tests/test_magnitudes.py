"""Toda magnitud viaja con su unidad y se redondea con LOS decimales de esa
unidad (RN-GER-010). Un monto sin divisa o una cantidad sin UdM no entran.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.app import create_app
from src.core.database import Base
from src.modules.inventory.infrastructure.models import CategoriaUdm, UnidadMedida
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Empresa
from src.shared import magnitudes
from src.shared.magnitudes import MagnitudInvalida, Unidad
from src.shared.models import Divisa


# --- Contrato puro (sin BD) --------------------------------------------------
def test_monto_sin_divisa_no_pasa():
    with pytest.raises(MagnitudInvalida, match="falta 'divisa'"):
        magnitudes.unidad_requerida({"monto": "2000"})


def test_cantidad_sin_unidad_de_medida_no_pasa():
    with pytest.raises(MagnitudInvalida, match="falta 'unidad_medida_id'"):
        magnitudes.unidad_requerida({"cantidad": "5"})


def test_unidad_sin_magnitud_no_pasa():
    with pytest.raises(MagnitudInvalida, match="ninguna clave monetaria"):
        magnitudes.unidad_requerida({"divisa": "PEN"})
    with pytest.raises(MagnitudInvalida, match="ninguna 'cantidad'"):
        magnitudes.unidad_requerida({"unidad_medida_id": str(uuid.uuid4())})


def test_dinero_y_magnitud_fisica_no_se_mezclan():
    with pytest.raises(MagnitudInvalida, match="a la vez"):
        magnitudes.unidad_requerida(
            {"monto": "1", "divisa": "PEN", "cantidad": "2", "unidad_medida_id": "x"}
        )


def test_adimensional_pasa_sin_unidad():
    assert magnitudes.unidad_requerida({"porcentaje": 2.5}) is None
    assert magnitudes.unidad_requerida({"dias": 5}) is None
    valor, display = magnitudes.canonizar({"dias": 5}, None)
    assert valor == {"dias": 5} and display is None


def test_redondeo_usa_los_decimales_de_la_unidad():
    dos = Unidad(decimales=2, etiqueta="S/", prefija=True)
    valor, display = magnitudes.canonizar({"monto": "2000.005", "divisa": "PEN"}, dos)
    assert valor["monto"] == "2000.01" and display == "S/ 2000.01"

    cero = Unidad(decimales=0, etiqueta="Unidad", prefija=False)
    valor, display = magnitudes.canonizar({"cantidad": 4.6, "unidad_medida_id": "x"}, cero)
    # Media botella no existe: 0 decimales redondea a entero.
    assert valor["cantidad"] == "5" and display == "5 Unidad"


def test_rango_se_formatea_completo():
    sol = Unidad(decimales=2, etiqueta="S/", prefija=True)
    valor, display = magnitudes.canonizar(
        {"minimo": 1500, "maximo": 2200, "divisa": "PEN"}, sol
    )
    assert valor["minimo"] == "1500.00" and valor["maximo"] == "2200.00"
    assert display == "S/ 1500.00 – S/ 2200.00"


def test_magnitud_no_numerica_no_pasa():
    sol = Unidad(decimales=2, etiqueta="S/", prefija=True)
    with pytest.raises(MagnitudInvalida, match="no es un número"):
        magnitudes.canonizar({"monto": "mucho", "divisa": "PEN"}, sol)


# --- A través de la API ------------------------------------------------------
@pytest.fixture()
def env():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from src.seeders.seed import seed

    datos = {}
    with TestSession() as s:
        seed(s)
        categoria = CategoriaUdm(nombre="Peso")
        s.add(categoria)
        s.flush()
        kilo = UnidadMedida(categoria_udm_id=categoria.id, nombre="Kilo", decimales=3)
        s.add(kilo)
        s.flush()
        datos["empresa_id"] = str(s.scalar(select(Empresa)).id)
        datos["kilo_id"] = str(kilo.id)
        s.commit()

    def _override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c, datos, TestSession


def _token(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "pin": "123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _proponer(client, h, datos, valor, modulo="inventory", codigo="param"):
    return client.post(
        "/api/v1/parametros",
        headers=h,
        json={
            "empresa_id": datos["empresa_id"],
            "modulo": modulo,
            "codigo": codigo,
            "valor": valor,
        },
    )


def test_seeder_deja_pen_con_dos_decimales(env):
    _, _, TestSession = env
    with TestSession() as s:
        pen = s.scalar(select(Divisa).where(Divisa.codigo == "PEN"))
    assert (pen.simbolo, pen.decimales, pen.activa) == ("S/", 2, True)


def test_monto_sin_divisa_es_409_y_con_divisa_se_formatea(env):
    client, datos, _ = env
    h = _token(client)

    # 409: `MagnitudInvalida` es una `ReglaNegocio` (RN-GER-010) y la traduce
    # el handler global de `core/error_handlers.py`.
    assert _proponer(client, h, datos, {"monto": "2000"}).status_code == 409

    r = _proponer(client, h, datos, {"monto": "2000", "divisa": "PEN"})
    assert r.status_code == 201
    assert r.json()["valor"]["monto"] == "2000.00"
    assert r.json()["valor_display"] == "S/ 2000.00"


def test_cantidad_usa_los_decimales_de_su_udm(env):
    client, datos, _ = env
    h = _token(client)
    r = _proponer(
        client, h, datos, {"cantidad": "5.5", "unidad_medida_id": datos["kilo_id"]}
    )
    assert r.status_code == 201
    # Kilo se sembró con 3 decimales: los gramos importan.
    assert r.json()["valor"]["cantidad"] == "5.500"
    assert r.json()["valor_display"] == "5.500 Kilo"


def test_divisa_o_udm_inexistente_es_409(env):
    client, datos, _ = env
    h = _token(client)
    assert _proponer(client, h, datos, {"monto": "1", "divisa": "XYZ"}).status_code == 409
    assert (
        _proponer(
            client, h, datos, {"cantidad": "1", "unidad_medida_id": str(uuid.uuid4())}
        ).status_code
        == 409
    )


def test_gerencia_no_puede_aprobar_un_monto_sin_divisa(env):
    """La puerta de atrás: modificar el valor al aprobar pasa por la misma
    validación que proponerlo."""
    client, datos, _ = env
    h = _token(client)
    propuesta_id = _proponer(client, h, datos, {"monto": "2000", "divisa": "PEN"}).json()["id"]

    malo = client.post(
        f"/api/v1/parametros/{propuesta_id}/aprobar",
        headers=h,
        json={"valor": {"monto": "3000"}},
    )
    assert malo.status_code == 409

    bueno = client.post(
        f"/api/v1/parametros/{propuesta_id}/aprobar",
        headers=h,
        json={"valor": {"monto": "3000.567", "divisa": "PEN"}},
    )
    assert bueno.status_code == 200
    assert bueno.json()["valor"]["monto"] == "3000.57"
    assert bueno.json()["valor_display"] == "S/ 3000.57"
