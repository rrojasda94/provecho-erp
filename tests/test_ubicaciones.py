"""La dirección anclada al mapa: qué se guarda, qué se rechaza y qué se borra.

Tres cosas que importan y fallan distinto:

- **Se guarda y vuelve.** Un punto que se escribe pero no se lee no sirve para
  calcular una distancia de reparto.
- **Media coordenada no entra.** Una latitud sin longitud pasa el `NOT NULL`
  —las dos columnas son nullable— y revienta recién cuando alguien cotiza un
  delivery, lejísimos de donde se originó.
- **La dirección a mano sigue siendo válida.** Es el caso que no se puede
  romper: sin clave de Google, sin internet o con una calle que Google no
  conoce, el alta tiene que seguir funcionando igual que antes (ADR-053).
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
from src.modules.users.infrastructure.models import (
    Empresa,
    Grupo,
    Persona,
    Sucursal,
)
from tests.conftest import auth_headers

# Una esquina real de Tarapoto, para que los números se lean como lo que son.
UBICACION = {
    "ubicacion_place_id": "ChIJ_provecho_plaza_de_armas",
    "ubicacion_lat": "-6.488430",
    "ubicacion_lng": "-76.365280",
    "ubicacion_plus_code": "57C8+2M Tarapoto",
    "ubicacion_distrito": "Tarapoto",
}


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
        ids["marca_id"] = str(s.scalar(select(Sucursal.marca_id)))
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


def _sucursal(ids: dict, **extra) -> dict:
    return {
        "marca_id": ids["marca_id"],
        "empresa_id": ids["empresa_id"],
        "nombre": "CH-Mapa",
        "direccion": "Jr. San Martín 456, Tarapoto",
        "tenencia": "alquilada",
        **extra,
    }


# --- Se guarda y vuelve -----------------------------------------------------
def test_la_sucursal_guarda_y_devuelve_su_punto_en_el_mapa(env):
    client, headers, ids, _ = env
    r = client.post(
        "/api/v1/sucursales", headers=headers, json=_sucursal(ids, **UBICACION)
    )
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["ubicacion_place_id"] == UBICACION["ubicacion_place_id"]
    assert float(cuerpo["ubicacion_lat"]) == pytest.approx(-6.48843)
    assert float(cuerpo["ubicacion_lng"]) == pytest.approx(-76.36528)
    assert cuerpo["ubicacion_distrito"] == "Tarapoto"


def test_se_puede_anclar_una_sucursal_que_ya_existia(env):
    """El caso normal al desplegar esto: las sucursales ya están cargadas con
    su dirección de texto y hay que ponerles el pin sin volver a crearlas."""
    client, headers, ids, _ = env
    r = client.patch(
        f"/api/v1/sucursales/{ids['sucursal_id']}", headers=headers, json=UBICACION
    )
    assert r.status_code == 200, r.text
    assert r.json()["ubicacion_place_id"] == UBICACION["ubicacion_place_id"]


# --- Lo que se rechaza ------------------------------------------------------
@pytest.mark.parametrize(
    "campo,valor",
    [
        ("ubicacion_lat", "-91"),
        ("ubicacion_lat", "91"),
        ("ubicacion_lng", "-181"),
        ("ubicacion_lng", "181"),
    ],
)
def test_una_coordenada_imposible_no_entra(env, campo, valor):
    client, headers, ids, _ = env
    datos = {**UBICACION, campo: valor}
    r = client.post("/api/v1/sucursales", headers=headers, json=_sucursal(ids, **datos))
    assert r.status_code == 422, r.text


def test_media_coordenada_no_es_un_punto(env):
    """Latitud sin longitud: las dos columnas son nullable, así que sin este
    validador el registro entra a la base y el error aparece meses después."""
    client, headers, ids, _ = env
    r = client.post(
        "/api/v1/sucursales",
        headers=headers,
        json=_sucursal(ids, ubicacion_lat="-6.48843"),
    )
    assert r.status_code == 422, r.text
    assert "ubicacion_lng" in r.text


def test_un_place_id_desmedido_no_entra(env):
    client, headers, ids, _ = env
    r = client.post(
        "/api/v1/sucursales",
        headers=headers,
        json=_sucursal(ids, ubicacion_place_id="x" * 256),
    )
    assert r.status_code == 422, r.text


# --- Lo que no se puede romper ----------------------------------------------
def test_una_direccion_escrita_a_mano_sigue_siendo_valida(env):
    """Sin clave de Google, sin internet, o con una calle que Google no
    conoce. Si este test se pone rojo, la integración dejó de ser opcional."""
    client, headers, ids, _ = env
    r = client.post("/api/v1/sucursales", headers=headers, json=_sucursal(ids))
    assert r.status_code == 201, r.text
    assert r.json()["ubicacion_place_id"] is None
    assert r.json()["ubicacion_lat"] is None


def test_el_proveedor_tambien_se_ancla(env):
    client, headers, ids, _ = env
    r = client.post(
        "/api/v1/purchases/proveedores",
        headers=headers,
        json={
            "empresa_id": ids["empresa_id"],
            "tipo": "juridico",
            "condicion_pago": "contado",
            "razon_social": "Distribuidora del Huallaga SAC",
            "ruc": "20600000123",
            "direccion": "Jr. Alegría Arias de Morey 123",
            **UBICACION,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["ubicacion_distrito"] == "Tarapoto"


# --- Ley 29733 --------------------------------------------------------------
def test_anonimizar_una_persona_tambien_borra_su_punto_en_el_mapa(env):
    """Las coordenadas de la casa de alguien son tan personales como su
    dirección escrita, o más: un punto en el mapa no admite la ambigüedad de
    un "por el mercado". Sin esto la anonimización dejaba la puerta exacta."""
    client, headers, _, TestSession = env
    persona = client.post(
        "/api/v1/personas",
        headers=headers,
        json={
            "nombres": "Ana",
            "apellidos": "Ríos",
            "tipo_documento": "dni",
            "numero_documento": "70123456",
            "domicilio": "Jr. Lima 200",
            **UBICACION,
        },
    )
    assert persona.status_code == 201, persona.text
    persona_id = persona.json()["id"]
    assert persona.json()["ubicacion_lat"] is not None

    r = client.post(
        f"/api/v1/personas/{persona_id}/anonimizar",
        headers=headers,
        json={"motivo": "solicitud del titular"},
    )
    assert r.status_code == 200, r.text

    with TestSession() as s:
        guardada = s.get(Persona, uuid.UUID(persona_id))
        assert guardada.domicilio is None
        assert guardada.ubicacion_place_id is None
        assert guardada.ubicacion_lat is None
        assert guardada.ubicacion_lng is None
        assert guardada.ubicacion_plus_code is None
        assert guardada.ubicacion_distrito is None


# --- El pin no sobrevive a un cambio de dirección ---------------------------
def test_corregir_la_direccion_sin_reanclar_borra_el_pin(env):
    """El escenario que cuesta plata: alguien corrige "Jr. Lima 200" por
    "Jr. Lima 400" tecleando, sin volver a elegir en el mapa. Si el pin viejo
    sobrevive, el texto dice una calle y el reparto cobra la distancia a
    otra."""
    client, headers, ids, _ = env
    creada = client.post(
        "/api/v1/sucursales", headers=headers, json=_sucursal(ids, **UBICACION)
    )
    sucursal_id = creada.json()["id"]

    r = client.patch(
        f"/api/v1/sucursales/{sucursal_id}",
        headers=headers,
        json={"direccion": "Jr. Otro Sitio 999"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["direccion"] == "Jr. Otro Sitio 999"
    assert r.json()["ubicacion_place_id"] is None
    assert r.json()["ubicacion_lat"] is None


def test_corregir_la_direccion_eligiendo_en_el_mapa_conserva_el_pin_nuevo(env):
    client, headers, ids, _ = env
    creada = client.post(
        "/api/v1/sucursales", headers=headers, json=_sucursal(ids, **UBICACION)
    )
    r = client.patch(
        f"/api/v1/sucursales/{creada.json()['id']}",
        headers=headers,
        json={
            "direccion": "Jr. Otro Sitio 999",
            **{**UBICACION, "ubicacion_place_id": "ChIJ_otro_sitio"},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["ubicacion_place_id"] == "ChIJ_otro_sitio"


def test_editar_otra_cosa_no_toca_el_pin(env):
    """Cambiar el nombre del local no puede desanclarlo: sería perder el dato
    en la mitad de las ediciones."""
    client, headers, ids, _ = env
    creada = client.post(
        "/api/v1/sucursales", headers=headers, json=_sucursal(ids, **UBICACION)
    )
    r = client.patch(
        f"/api/v1/sucursales/{creada.json()['id']}",
        headers=headers,
        json={"nombre": "CH-Mapa Renombrada"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ubicacion_place_id"] == UBICACION["ubicacion_place_id"]


def test_el_desanclaje_queda_en_la_auditoria(env):
    """Perder un dato sin registro es cómo alguien pasa una tarde buscando
    quién le borró las coordenadas a la sucursal."""
    from src.shared.models.audit_log import AuditLog

    client, headers, ids, TestSession = env
    creada = client.post(
        "/api/v1/sucursales", headers=headers, json=_sucursal(ids, **UBICACION)
    )
    client.patch(
        f"/api/v1/sucursales/{creada.json()['id']}",
        headers=headers,
        json={"direccion": "Jr. Otro Sitio 999"},
    )
    with TestSession() as s:
        registros = list(
            s.scalars(select(AuditLog).where(AuditLog.entidad == "sucursal"))
        )
    ediciones = [r for r in registros if r.accion == "editar"]
    assert ediciones, "la edición no quedó auditada"
    assert "ubicacion_place_id" in (ediciones[-1].datos_antes or {})
