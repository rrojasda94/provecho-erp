"""CRUD de organización por API: grupo, empresa, marca, licencia de marca,
sucursal y almacén.

Hasta ahora esto solo lo escribía el seeder. Lo que se prueba acá son las
reglas que el seeder daba por buenas porque las tipeaba a mano: la licencia
como requisito de una sucursal, la coherencia de empresa en los almacenes,
la baja negada con dependientes vivos y el alcance por tenant (ADR-004).
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401  (puebla Base.metadata)
from src.core.app import create_app
from src.core.database import Base
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Empresa, Grupo, Sucursal
from src.shared.models.audit_log import AuditLog
from tests.conftest import auth_headers


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
        ids["grupo_id"] = str(s.scalar(select(Grupo.id)))
        ids["empresa_id"] = str(s.scalar(select(Empresa.id)))
        ids["sucursal_id"] = str(s.scalar(select(Sucursal.id)))
        cabeceras = auth_headers(s)
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
        yield c, cabeceras, ids, TestSession


EMPRESA_NUEVA = {
    "razon_social": "Majambo Logistica SAC",
    "ruc": "20600000001",
    "domicilio_fiscal": "Jr. Comercio 100, Tarapoto",
    "tipo": "logistica",
}


# --- Grupo y empresa --------------------------------------------------------
def test_crear_y_editar_grupo(env):
    client, headers, _, _ = env
    r = client.post("/api/v1/grupos", headers=headers, json={"nombre": "Grupo Nuevo"})
    assert r.status_code == 201, r.text
    grupo_id = r.json()["id"]

    assert client.post(
        "/api/v1/grupos", headers=headers, json={"nombre": "Grupo Nuevo"}
    ).status_code == 409

    r = client.patch(
        f"/api/v1/grupos/{grupo_id}", headers=headers, json={"nombre": "Grupo Renombrado"}
    )
    assert r.status_code == 200
    assert r.json()["nombre"] == "Grupo Renombrado"
    assert {g["nombre"] for g in client.get("/api/v1/grupos", headers=headers).json()} >= {
        "Grupo Renombrado"
    }


def test_crear_empresa_y_ruc_unico(env):
    client, headers, ids, _ = env
    r = client.post(
        "/api/v1/empresas", headers=headers, json={**EMPRESA_NUEVA, "grupo_id": ids["grupo_id"]}
    )
    assert r.status_code == 201, r.text
    assert r.json()["zona_tributaria"] == "general"

    repetida = client.post(
        "/api/v1/empresas", headers=headers, json={**EMPRESA_NUEVA, "grupo_id": ids["grupo_id"]}
    )
    assert repetida.status_code == 409


def test_ruc_mal_formado_muere_en_el_borde(env):
    client, headers, ids, _ = env
    r = client.post(
        "/api/v1/empresas",
        headers=headers,
        json={**EMPRESA_NUEVA, "ruc": "123", "grupo_id": ids["grupo_id"]},
    )
    assert r.status_code == 422


def test_editar_empresa_audita_y_no_mueve_de_grupo(env):
    client, headers, ids, _ = env
    r = client.patch(
        f"/api/v1/empresas/{ids['empresa_id']}",
        headers=headers,
        json={"contacto": "gerencia@majambo.pe", "grupo_id": "otro"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["contacto"] == "gerencia@majambo.pe"
    # `grupo_id` no es editable: el campo extra se ignora, no mueve nada.
    assert r.json()["grupo_id"] == ids["grupo_id"]


def test_baja_de_empresa_con_sucursales_409(env):
    client, headers, ids, _ = env
    r = client.delete(f"/api/v1/empresas/{ids['empresa_id']}", headers=headers)
    assert r.status_code == 409
    assert "sucursales" in r.json()["detail"]


def test_baja_de_empresa_vacia_ok(env):
    client, headers, ids, _ = env
    nueva = client.post(
        "/api/v1/empresas", headers=headers, json={**EMPRESA_NUEVA, "grupo_id": ids["grupo_id"]}
    ).json()

    assert client.delete(f"/api/v1/empresas/{nueva['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/empresas/{nueva['id']}", headers=headers).status_code == 404


# --- Marca y licencia -------------------------------------------------------
def test_marca_licencia_y_sucursal(env):
    client, headers, ids, _ = env
    marca = client.post(
        "/api/v1/marcas",
        headers=headers,
        json={"grupo_id": ids["grupo_id"], "nombre": "Charlie's Burgers", "tipo": "restaurante"},
    )
    assert marca.status_code == 201, marca.text
    marca_id = marca.json()["id"]

    # Sin licencia, la sucursal no puede existir.
    sin_licencia = client.post(
        "/api/v1/sucursales",
        headers=headers,
        json={
            "marca_id": marca_id,
            "empresa_id": ids["empresa_id"],
            "nombre": "CH3",
            "direccion": "Av. Nueva 300",
            "tenencia": "alquilada",
        },
    )
    assert sin_licencia.status_code == 409
    assert "licencia" in sin_licencia.json()["detail"]

    licencia = client.post(
        f"/api/v1/empresas/{ids['empresa_id']}/marcas",
        headers=headers,
        json={"marca_id": marca_id},
    )
    assert licencia.status_code == 201
    # Idempotente: otorgarla de nuevo devuelve la misma fila.
    otra = client.post(
        f"/api/v1/empresas/{ids['empresa_id']}/marcas",
        headers=headers,
        json={"marca_id": marca_id},
    )
    assert otra.json()["id"] == licencia.json()["id"]

    con_licencia = client.post(
        "/api/v1/sucursales",
        headers=headers,
        json={
            "marca_id": marca_id,
            "empresa_id": ids["empresa_id"],
            "nombre": "CH3",
            "direccion": "Av. Nueva 300",
            "tenencia": "alquilada",
        },
    )
    assert con_licencia.status_code == 201, con_licencia.text
    assert con_licencia.json()["estado"] == "activa"


def test_revocar_licencia_con_sucursal_activa_409(env):
    client, headers, ids, TestSession = env
    with TestSession() as s:
        marca_id = str(s.scalar(select(Sucursal.marca_id)))

    r = client.delete(
        f"/api/v1/empresas/{ids['empresa_id']}/marcas/{marca_id}", headers=headers
    )
    assert r.status_code == 409


def test_baja_de_marca_licenciada_409(env):
    client, headers, ids, TestSession = env
    with TestSession() as s:
        marca_id = str(s.scalar(select(Sucursal.marca_id)))

    assert client.delete(f"/api/v1/marcas/{marca_id}", headers=headers).status_code == 409


def test_editar_marca_nombre_duplicado_409(env):
    client, headers, ids, _ = env
    client.post(
        "/api/v1/marcas",
        headers=headers,
        json={"grupo_id": ids["grupo_id"], "nombre": "Marca A", "tipo": "restaurante"},
    )
    b = client.post(
        "/api/v1/marcas",
        headers=headers,
        json={"grupo_id": ids["grupo_id"], "nombre": "Marca B", "tipo": "delivery"},
    ).json()

    r = client.patch(
        f"/api/v1/marcas/{b['id']}", headers=headers, json={"nombre": "Marca A"}
    )
    assert r.status_code == 409


# --- Sucursal ---------------------------------------------------------------
def test_cerrar_local_es_cambiar_estado(env):
    client, headers, ids, _ = env
    r = client.patch(
        f"/api/v1/sucursales/{ids['sucursal_id']}",
        headers=headers,
        json={"estado": "inactiva"},
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "inactiva"
    # Sigue existiendo: es el ancla de sus ventas, cajas y trabajadores.
    assert client.get(
        f"/api/v1/sucursales/{ids['sucursal_id']}", headers=headers
    ).status_code == 200


# --- Almacén ----------------------------------------------------------------
def test_almacen_de_sucursal_exige_sucursal(env):
    client, headers, ids, _ = env
    r = client.post(
        "/api/v1/almacenes",
        headers=headers,
        json={
            "empresa_id": ids["empresa_id"],
            "nombre": "Almacén CH1",
            "tipo": "sucursal",
        },
    )
    assert r.status_code == 409
    assert "sucursal_id" in r.json()["detail"]


def test_almacen_con_abastecedor_y_baja_encadenada(env):
    client, headers, ids, _ = env
    central = client.get("/api/v1/almacenes", headers=headers).json()[0]

    hijo = client.post(
        "/api/v1/almacenes",
        headers=headers,
        json={
            "empresa_id": ids["empresa_id"],
            "sucursal_id": ids["sucursal_id"],
            "nombre": "Almacén CH1",
            "tipo": "sucursal",
            "almacen_abastecedor_id": central["id"],
        },
    )
    assert hijo.status_code == 201, hijo.text

    # El central abastece a alguien: no se da de baja sin desengancharlo.
    negada = client.delete(f"/api/v1/almacenes/{central['id']}", headers=headers)
    assert negada.status_code == 409

    assert client.delete(
        f"/api/v1/almacenes/{hijo.json()['id']}", headers=headers
    ).status_code == 204
    assert client.delete(f"/api/v1/almacenes/{central['id']}", headers=headers).status_code == 204


def test_editar_almacen_de_sucursal_sin_repetir_la_sucursal(env):
    """Un PATCH que solo renombra no menciona `sucursal_id`, y eso no puede
    hacer que el almacén deje de cumplir su propia regla de tipo."""
    client, headers, ids, _ = env
    almacen = client.post(
        "/api/v1/almacenes",
        headers=headers,
        json={
            "empresa_id": ids["empresa_id"],
            "sucursal_id": ids["sucursal_id"],
            "nombre": "Almacén CH1",
            "tipo": "sucursal",
        },
    ).json()

    r = client.patch(
        f"/api/v1/almacenes/{almacen['id']}",
        headers=headers,
        json={"nombre": "Almacén CH1 - piso 2"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["sucursal_id"] == ids["sucursal_id"]


def test_almacen_no_se_abastece_de_si_mismo(env):
    client, headers, ids, _ = env
    central = client.get("/api/v1/almacenes", headers=headers).json()[0]
    r = client.patch(
        f"/api/v1/almacenes/{central['id']}",
        headers=headers,
        json={"almacen_abastecedor_id": central["id"]},
    )
    assert r.status_code == 409


def test_almacen_de_sucursal_de_otra_empresa_409(env):
    client, headers, ids, _ = env
    otra = client.post(
        "/api/v1/empresas", headers=headers, json={**EMPRESA_NUEVA, "grupo_id": ids["grupo_id"]}
    ).json()
    r = client.post(
        "/api/v1/almacenes",
        headers=headers,
        json={
            "empresa_id": otra["id"],
            "sucursal_id": ids["sucursal_id"],
            "nombre": "Almacén ajeno",
            "tipo": "sucursal",
        },
    )
    assert r.status_code == 409
    assert "otra empresa" in r.json()["detail"]


# --- Permisos y alcance por tenant (ADR-004) --------------------------------
def _usuario_de_empresa(
    client,
    headers,
    TestSession,
    ids,
    username="jefe_local",
    codigos=("organizacion.gestionar",),
):
    """Usuario con los permisos que se le pidan y alcance a una sucursal: su
    token trae `empresa_id`, así que NO es superusuario."""
    permisos = client.get("/api/v1/permisos", headers=headers).json()
    rol = client.post(
        "/api/v1/roles", headers=headers, json={"nombre": f"rol_{username}"}
    ).json()
    for codigo in codigos:
        permiso_id = next(p["id"] for p in permisos if p["codigo"] == codigo)
        assert (
            client.post(
                f"/api/v1/roles/{rol['id']}/permisos",
                headers=headers,
                json={"permiso_id": permiso_id},
            ).status_code
            == 204
        )
    usuario = client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": username, "pin": "123456", "tipo": "humano"},
    ).json()
    client.post(
        f"/api/v1/users/{usuario['id']}/roles", headers=headers, json={"rol_id": rol["id"]}
    )
    client.post(
        f"/api/v1/users/{usuario['id']}/sucursales",
        headers=headers,
        json={"sucursal_id": ids["sucursal_id"]},
    )
    with TestSession() as s:
        return auth_headers(s, username)


def test_sin_permiso_no_administra_la_organizacion(env):
    client, headers, ids, TestSession = env
    client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": "cajera", "pin": "123456", "tipo": "humano"},
    )
    with TestSession() as s:
        cajera = auth_headers(s, "cajera")

    assert client.post("/api/v1/grupos", headers=cajera, json={"nombre": "X"}).status_code == 403
    assert (
        client.post(
            "/api/v1/marcas",
            headers=cajera,
            json={"grupo_id": ids["grupo_id"], "nombre": "X", "tipo": "restaurante"},
        ).status_code
        == 403
    )


def test_admin_de_empresa_no_funda_empresas_ni_grupos(env):
    client, headers, ids, TestSession = env
    local = _usuario_de_empresa(client, headers, TestSession, ids)

    assert client.post("/api/v1/grupos", headers=local, json={"nombre": "X"}).status_code == 403
    assert (
        client.post(
            "/api/v1/empresas", headers=local, json={**EMPRESA_NUEVA, "grupo_id": ids["grupo_id"]}
        ).status_code
        == 403
    )
    # Su empresa sí la administra, y el listado le muestra solo la suya.
    suyas = client.get("/api/v1/empresas", headers=local)
    assert suyas.status_code == 200
    assert [e["id"] for e in suyas.json()] == [ids["empresa_id"]]

    # Lo mismo con el grupo: ve el suyo, no el listado del ERP.
    client.post("/api/v1/grupos", headers=headers, json={"nombre": "Otro Grupo"})
    grupos = client.get("/api/v1/grupos", headers=local)
    assert [g["id"] for g in grupos.json()] == [ids["grupo_id"]]


def test_admin_de_empresa_crea_sucursal_en_la_suya(env):
    client, headers, ids, TestSession = env
    local = _usuario_de_empresa(client, headers, TestSession, ids)
    with TestSession() as s:
        marca_id = str(s.scalar(select(Sucursal.marca_id)))

    r = client.post(
        "/api/v1/sucursales",
        headers=local,
        json={
            "marca_id": marca_id,
            "nombre": "CH9",
            "direccion": "Av. Nueva 900",
            "tenencia": "alquilada",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["empresa_id"] == ids["empresa_id"]


def test_no_se_puede_crear_sucursal_en_empresa_ajena(env):
    client, headers, ids, TestSession = env
    otra = client.post(
        "/api/v1/empresas", headers=headers, json={**EMPRESA_NUEVA, "grupo_id": ids["grupo_id"]}
    ).json()
    local = _usuario_de_empresa(client, headers, TestSession, ids)
    with TestSession() as s:
        marca_id = str(s.scalar(select(Sucursal.marca_id)))

    r = client.post(
        "/api/v1/sucursales",
        headers=local,
        json={
            "marca_id": marca_id,
            "empresa_id": otra["id"],
            "nombre": "CH9",
            "direccion": "Av. Nueva 900",
            "tenencia": "alquilada",
        },
    )
    assert r.status_code == 403


# --- Alcance por sucursal de una cuenta (usuario_sucursal, ADR-061) ----------
def _nueva_sucursal(client, headers, nombre):
    marca_id = client.get("/api/v1/sucursales", headers=headers).json()[0]["marca_id"]
    r = client.post(
        "/api/v1/sucursales",
        headers=headers,
        json={
            "marca_id": marca_id,
            "nombre": nombre,
            "direccion": f"Av. {nombre} 100",
            "tenencia": "alquilada",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _sucursal_de_otra_empresa(TestSession, ids):
    """Directo a la BD: el alta por API exige licencia de marca para esa
    empresa (`test_sucursal_exige_licencia`) y acá lo que se prueba es otra
    cosa — el alcance de una cuenta, no el alta del local."""
    with TestSession() as s:
        otra = Empresa(
            grupo_id=uuid.UUID(ids["grupo_id"]),
            razon_social="Majambo Ajena SAC",
            ruc="20600000009",
            domicilio_fiscal="Jr. Ajeno 100",
            tipo="operativa",
        )
        s.add(otra)
        s.flush()
        sucursal = Sucursal(
            marca_id=s.scalar(select(Sucursal.marca_id)),
            empresa_id=otra.id,
            nombre="Local ajeno",
            direccion="Jr. Ajeno 100",
            tenencia="alquilada",
        )
        s.add(sucursal)
        s.commit()
        return str(sucursal.id)


def _cuenta(client, headers, username):
    return client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": username, "pin": "123456", "tipo": "humano"},
    ).json()["id"]


def test_alcance_por_sucursal_se_asigna_lista_y_quita(env):
    client, headers, ids, TestSession = env
    usuario_id = _cuenta(client, headers, "cajera_ch1")
    url = f"/api/v1/users/{usuario_id}/sucursales"

    assert client.get(url, headers=headers).json() == []

    assert client.post(
        url, headers=headers, json={"sucursal_id": ids["sucursal_id"]}
    ).status_code == 204
    asignadas = client.get(url, headers=headers).json()
    assert [s["id"] for s in asignadas] == [ids["sucursal_id"]]
    assert asignadas[0]["nombre"]

    # Repetir no duplica ni falla: la pantalla puede reintentar.
    assert client.post(
        url, headers=headers, json={"sucursal_id": ids["sucursal_id"]}
    ).status_code == 204
    assert len(client.get(url, headers=headers).json()) == 1

    assert client.delete(f"{url}/{ids['sucursal_id']}", headers=headers).status_code == 204
    assert client.get(url, headers=headers).json() == []

    # Repartir y sacar acceso a datos deja rastro: sin esto no había forma de
    # responder quién podía ver ese local y desde cuándo.
    with TestSession() as s:
        acciones = set(
            s.scalars(
                select(AuditLog.accion).where(AuditLog.entidad == "usuario_sucursal")
            )
        )
    assert acciones == {"asignar_sucursal", "quitar_sucursal"}


def test_supervisor_alcanza_varias_sucursales(env):
    """Un supervisor sobre varios locales son varias filas, no una entidad
    nueva (ADR-061): `usuario_sucursal` ya es N a N."""
    client, headers, ids, TestSession = env
    segunda = _nueva_sucursal(client, headers, "CH2")
    usuario_id = _cuenta(client, headers, "supervisor_zona")
    url = f"/api/v1/users/{usuario_id}/sucursales"

    for sucursal_id in (ids["sucursal_id"], segunda):
        assert client.post(
            url, headers=headers, json={"sucursal_id": sucursal_id}
        ).status_code == 204

    assert {s["id"] for s in client.get(url, headers=headers).json()} == {
        ids["sucursal_id"],
        segunda,
    }

    # El alcance recién le llega a esa persona cuando su sesión emite token.
    with TestSession() as s:
        supervisor = auth_headers(s, "supervisor_zona")
    yo = client.get("/api/v1/users/me", headers=supervisor).json()
    assert set(yo["sucursales"]) == {ids["sucursal_id"], segunda}


def test_no_se_asigna_sucursal_de_empresa_ajena(env):
    """Sin el chequeo de tenant, quien administra las cuentas de su empresa
    podía darle acceso a los datos del local de otra empresa del grupo."""
    client, headers, ids, TestSession = env
    ajena = _sucursal_de_otra_empresa(TestSession, ids)

    admin_local = _usuario_de_empresa(
        client,
        headers,
        TestSession,
        ids,
        username="jefe_cuentas",
        codigos=("users.gestionar", "organizacion.gestionar"),
    )
    usuario_id = _cuenta(client, headers, "cajera_ajena")

    r = client.post(
        f"/api/v1/users/{usuario_id}/sucursales",
        headers=admin_local,
        json={"sucursal_id": ajena},
    )
    assert r.status_code == 403

    # La cuenta de administración del grupo sí puede: administra todas las
    # empresas, igual que en el alta de sucursales.
    assert client.post(
        f"/api/v1/users/{usuario_id}/sucursales",
        headers=headers,
        json={"sucursal_id": ajena},
    ).status_code == 204


def test_asignar_sucursal_inexistente_404(env):
    client, headers, ids, _ = env
    usuario_id = _cuenta(client, headers, "cajera_fantasma")
    r = client.post(
        f"/api/v1/users/{usuario_id}/sucursales",
        headers=headers,
        json={"sucursal_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert r.status_code == 404
