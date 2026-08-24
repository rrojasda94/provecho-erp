"""Alta y edición de puntos de venta por API — la caja de una sucursal.

Hasta ahora esto solo lo escribía el seeder, así que una sucursal recién
creada no podía vender: el PDV arranca pidiendo el punto de venta. Lo que se
prueba acá son las reglas que el seeder daba por buenas porque tipeaba las
series a mano — sobre todo la unicidad de serie dentro de la empresa
(RN-CPP-007), que **no** tiene constraint en la base y solo existe en el caso
de uso (ADR-059).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401  (puebla Base.metadata)
from src.core.app import create_app
from src.core.database import Base
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Sucursal
from src.shared.models.audit_log import AuditLog
from tests.conftest import auth_headers

RUTA = "/api/v1/sales/puntos-venta"


@pytest.fixture()
def env():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        # El seeder deja dos locales de la misma empresa (CH1 y CH2): es lo
        # que hace probable que la serie no se repita *entre sucursales*.
        sucursales = list(s.scalars(select(Sucursal).order_by(Sucursal.nombre)))
        ids["sucursal_id"] = str(sucursales[0].id)
        ids["otra_sucursal_id"] = str(sucursales[1].id)
        cabeceras = auth_headers(s)
        cabeceras_cajero = auth_headers(s, username="cajero1")
        s.commit()

    app = create_app()

    def _override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c, cabeceras, cabeceras_cajero, ids, TestSession


def caja(sucursal_id: str, **extra) -> dict:
    cuerpo = {
        "sucursal_id": sucursal_id,
        "canal": "trabajador",
        "politica_pago": "al_finalizar",
        "serie_boleta": "B001",
        "serie_factura": "F001",
        "serie_nc_boleta": "BC01",
        "serie_nc_factura": "FC01",
        "modalidades_habilitadas": ["mesa", "takeout", "delivery"],
    }
    return cuerpo | extra


# --- Alta -------------------------------------------------------------------
def test_crear_punto_venta(env):
    client, headers, _, ids, _ = env
    r = client.post(RUTA, headers=headers, json=caja(ids["sucursal_id"]))
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["serie_boleta"] == "B001"
    assert cuerpo["serie_nc_boleta"] == "BC01"
    assert cuerpo["canal"] == "trabajador"
    assert cuerpo["sucursal_id"] == ids["sucursal_id"]


def test_la_serie_se_normaliza_a_mayusculas(env):
    client, headers, _, ids, _ = env
    r = client.post(
        RUTA,
        headers=headers,
        json=caja(ids["sucursal_id"], serie_boleta=" b001 ", serie_factura="f001"),
    )
    assert r.status_code == 201, r.text
    assert r.json()["serie_boleta"] == "B001"
    assert r.json()["serie_factura"] == "F001"


def test_sucursal_inexistente(env):
    """404, no 500: en SQLite la FK no se valida, así que el caso de uso
    tiene que mirar la sucursal antes de insertar."""
    client, headers, _, _, _ = env
    r = client.post(
        RUTA, headers=headers, json=caja("00000000-0000-0000-0000-000000000001")
    )
    assert r.status_code == 404, r.text


# --- Series (RN-CPP-007 / RN-CPP-009) ---------------------------------------
def test_serie_duplicada_en_la_empresa(env):
    """La otra sucursal es de la misma empresa: el correlativo es único por
    `(empresa, serie)`, así que B001 ya está tomada. No hay constraint que
    ataje esto — solo el caso de uso."""
    client, headers, _, ids, _ = env
    assert client.post(
        RUTA, headers=headers, json=caja(ids["sucursal_id"])
    ).status_code == 201

    r = client.post(RUTA, headers=headers, json=caja(ids["otra_sucursal_id"]))
    assert r.status_code == 409, r.text
    assert "B001" in r.json()["detail"]


def test_serie_choca_contra_una_nota_de_credito(env):
    """Una serie no deja de estar ocupada por ser la de las NC de otra caja."""
    client, headers, _, ids, _ = env
    client.post(RUTA, headers=headers, json=caja(ids["sucursal_id"]))

    r = client.post(
        RUTA,
        headers=headers,
        json=caja(
            ids["otra_sucursal_id"],
            serie_boleta="BC01",  # la usa la primera caja como serie_nc_boleta
            serie_factura="F002",
            serie_nc_boleta="BC02",
            serie_nc_factura="FC02",
        ),
    )
    assert r.status_code == 409, r.text


def test_series_repetidas_entre_si(env):
    """La NC numera aparte del documento que corrige (RN-CPP-009)."""
    client, headers, _, ids, _ = env
    r = client.post(
        RUTA,
        headers=headers,
        json=caja(ids["sucursal_id"], serie_nc_boleta="B001"),
    )
    assert r.status_code == 409, r.text


@pytest.mark.parametrize("serie", ["B1", "X001", "B0011", "", "001"])
def test_serie_con_formato_invalido(env, serie):
    client, headers, _, ids, _ = env
    r = client.post(
        RUTA, headers=headers, json=caja(ids["sucursal_id"], serie_boleta=serie)
    )
    assert r.status_code == 409, r.text


# --- Canal y política de pago -----------------------------------------------
def test_kiosko_exige_pago_adelantado(env):
    """RN-POS-005: sin cajero delante, nadie persigue el pago al final."""
    client, headers, _, ids, _ = env
    r = client.post(
        RUTA,
        headers=headers,
        json=caja(ids["sucursal_id"], canal="kiosko", politica_pago="al_finalizar"),
    )
    assert r.status_code == 409, r.text


def test_hardware_id_con_canal_web(env):
    """Se rechaza en vez de anularlo en silencio: quien lo mandó cree que
    tiene una caja física y no la tiene."""
    client, headers, _, ids, _ = env
    r = client.post(
        RUTA,
        headers=headers,
        json=caja(
            ids["sucursal_id"],
            canal="web",
            politica_pago="adelantado",
            hardware_id="TPV-01",
        ),
    )
    assert r.status_code == 409, r.text


def test_modalidades_vacias(env):
    """Una caja que no atiende de ninguna forma no tiene para qué existir."""
    client, headers, _, ids, _ = env
    r = client.post(
        RUTA, headers=headers, json=caja(ids["sucursal_id"], modalidades_habilitadas=[])
    )
    assert r.status_code == 409, r.text


# --- Edición ----------------------------------------------------------------
def test_editar_punto_venta(env):
    client, headers, _, ids, _ = env
    punto_id = client.post(
        RUTA, headers=headers, json=caja(ids["sucursal_id"])
    ).json()["id"]

    r = client.patch(
        f"{RUTA}/{punto_id}",
        headers=headers,
        json={"modalidades_habilitadas": ["mesa"], "serie_boleta": "B009"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["modalidades_habilitadas"] == ["mesa"]
    assert r.json()["serie_boleta"] == "B009"


def test_guardar_sin_tocar_la_serie_no_choca_consigo_mismo(env):
    """El clásico: sin `excluir_id`, la caja se rechaza contra su propia
    serie y editar el horario se vuelve imposible."""
    client, headers, _, ids, _ = env
    punto_id = client.post(
        RUTA, headers=headers, json=caja(ids["sucursal_id"])
    ).json()["id"]

    r = client.patch(
        f"{RUTA}/{punto_id}",
        headers=headers,
        json={"serie_boleta": "B001", "modalidades_habilitadas": ["takeout"]},
    )
    assert r.status_code == 200, r.text


def test_editar_punto_venta_inexistente(env):
    client, headers, _, _, _ = env
    r = client.patch(
        f"{RUTA}/00000000-0000-0000-0000-000000000001", headers=headers, json={}
    )
    assert r.status_code == 404, r.text


# --- Listado y permisos -----------------------------------------------------
def test_listar_por_empresa_y_por_sucursal(env):
    client, headers, _, ids, _ = env
    client.post(RUTA, headers=headers, json=caja(ids["sucursal_id"]))
    client.post(
        RUTA,
        headers=headers,
        json=caja(
            ids["otra_sucursal_id"],
            serie_boleta="B002",
            serie_factura="F002",
            serie_nc_boleta="BC02",
            serie_nc_factura="FC02",
        ),
    )

    todas = client.get(RUTA, headers=headers)
    assert todas.status_code == 200, todas.text
    assert len(todas.json()) == 2

    una = client.get(RUTA, headers=headers, params={"sucursal_id": ids["sucursal_id"]})
    assert una.status_code == 200
    assert [p["serie_boleta"] for p in una.json()] == ["B001"]


def test_el_cajero_lee_pero_no_da_de_alta(env):
    """`sales.leer` abre el PDV; dar de alta una caja es asignar series SUNAT
    y lo firma quien administra la organización (ADR-059)."""
    client, headers, cajero, ids, _ = env
    client.post(RUTA, headers=headers, json=caja(ids["sucursal_id"]))

    assert client.post(
        RUTA, headers=cajero, json=caja(ids["otra_sucursal_id"], serie_boleta="B002")
    ).status_code == 403
    assert client.get(
        RUTA, headers=cajero, params={"sucursal_id": ids["sucursal_id"]}
    ).status_code == 200


def test_auditoria(env):
    client, headers, _, ids, TestSession = env
    client.post(RUTA, headers=headers, json=caja(ids["sucursal_id"]))
    punto_id = client.get(RUTA, headers=headers).json()[0]["id"]
    client.patch(
        f"{RUTA}/{punto_id}", headers=headers, json={"modalidades_habilitadas": ["mesa"]}
    )

    with TestSession() as s:
        acciones = [
            a.accion
            for a in s.scalars(
                select(AuditLog).where(AuditLog.entidad == "punto_venta")
            )
        ]
    assert sorted(acciones) == ["crear", "editar"]
