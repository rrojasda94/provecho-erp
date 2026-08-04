"""Paginación de colecciones (ADR-026).

Prueba el sobre y el corte contra un listado real de la API —`/personas`,
que no necesita organización sembrada— más el helper en aislamiento.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.app import create_app
from src.core.database import Base
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Persona
from src.shared.paginacion import PAGE_SIZE_MAXIMO, Paginacion, paginar


@pytest.fixture()
def env():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from src.seeders.seed import seed

    with TestSession() as s:
        seed(s)
        for i in range(7):
            s.add(
                Persona(
                    nombres=f"Persona{i:02d}",
                    apellidos=f"Apellido{i:02d}",
                    tipo_documento="dni",
                    numero_documento=f"1000000{i}",
                )
            )
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
        yield c, TestSession


def _token(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "pin": "123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- El helper ---------------------------------------------------------------
def test_el_total_cuenta_todo_y_los_items_solo_la_pagina(env):
    _client, TestSession = env
    with TestSession() as s:
        pagina = paginar(
            s, select(Persona).order_by(Persona.apellidos), Paginacion(1, 3)
        )
    assert pagina["total"] == 7
    assert len(pagina["items"]) == 3
    assert pagina["page"] == 1


def test_la_ultima_pagina_trae_el_resto_sin_rellenar(env):
    _client, TestSession = env
    with TestSession() as s:
        pagina = paginar(
            s, select(Persona).order_by(Persona.apellidos), Paginacion(3, 3)
        )
    assert pagina["total"] == 7
    assert len(pagina["items"]) == 1


def test_una_pagina_pasada_del_final_viene_vacia_pero_con_total(env):
    """No es un error: el cliente que pide la página 9 de 3 necesita saber
    que hay 7 filas para volver a una válida."""
    _client, TestSession = env
    with TestSession() as s:
        pagina = paginar(s, select(Persona), Paginacion(9, 3))
    assert pagina["items"] == []
    assert pagina["total"] == 7


def test_las_paginas_no_repiten_ni_pierden_filas(env):
    _client, TestSession = env
    consulta = select(Persona).order_by(Persona.apellidos)
    with TestSession() as s:
        vistos = [
            p.numero_documento
            for pagina in (1, 2, 3)
            for p in paginar(s, consulta, Paginacion(pagina, 3))["items"]
        ]
    assert len(vistos) == len(set(vistos)) == 7


# --- El endpoint -------------------------------------------------------------
def test_el_listado_devuelve_el_sobre_completo(env):
    client, _ = env
    r = client.get("/api/v1/personas?page=1&page_size=2", headers=_token(client))
    assert r.status_code == 200
    cuerpo = r.json()
    assert set(cuerpo) == {"items", "total", "page", "page_size"}
    assert cuerpo["total"] == 7
    assert len(cuerpo["items"]) == 2
    assert cuerpo["page_size"] == 2


def test_sin_parametros_trae_la_primera_pagina(env):
    client, _ = env
    cuerpo = client.get("/api/v1/personas", headers=_token(client)).json()
    assert cuerpo["page"] == 1
    assert cuerpo["page_size"] == 50


def test_page_size_desmedido_se_rechaza(env):
    """El techo existe para que `page_size=1000000` no sea una forma cómoda
    de tumbar la API con una sola petición autenticada."""
    client, _ = env
    r = client.get(
        f"/api/v1/personas?page_size={PAGE_SIZE_MAXIMO + 1}", headers=_token(client)
    )
    assert r.status_code == 422


def test_pagina_cero_se_rechaza(env):
    client, _ = env
    r = client.get("/api/v1/personas?page=0", headers=_token(client))
    assert r.status_code == 422


def test_el_filtro_se_respeta_en_el_total(env):
    """El total es el de la consulta filtrada, no el de la tabla: si no,
    el cliente dibuja doce páginas para tres resultados."""
    client, _ = env
    cuerpo = client.get("/api/v1/personas?q=Persona03", headers=_token(client)).json()
    assert cuerpo["total"] == 1
    assert len(cuerpo["items"]) == 1
