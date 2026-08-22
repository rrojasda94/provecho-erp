"""Tests del tablero de contratación: convocatoria, formulario público de
postulación y avance del postulante hasta trabajador.
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
from src.modules.users.infrastructure.models import Empresa, Persona, Rol, Usuario, UsuarioRol
from src.modules.users.infrastructure.security import hash_pin


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
        empresa = s.scalar(select(Empresa))
        cocinero = Usuario(username="cocinero1", pin_hash=hash_pin("222222"), tipo="humano")
        s.add(cocinero)
        s.flush()
        rol_cocinero = s.scalar(select(Rol).where(Rol.nombre == "cocinero"))
        s.add(UsuarioRol(usuario_id=cocinero.id, rol_id=rol_cocinero.id))
        ids.update(empresa_id=str(empresa.id))
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
        yield c, ids, TestSession


def _token(client, username="admin", pin="123456"):
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _crear_convocatoria(client, headers, ids, **overrides):
    body = {
        "empresa_id": ids["empresa_id"],
        "puesto": "Pizzero",
        "motivo": "refuerzo",
        "perfil_puesto": "cocina",
        "vacantes": 1,
    }
    body.update(overrides)
    return client.post("/api/v1/rrhh/convocatorias", headers=headers, json=body)


def _publicar(client, headers, convocatoria_id, **overrides):
    body = {"fecha_publicacion": "2026-08-01"}
    body.update(overrides)
    return client.post(
        f"/api/v1/rrhh/convocatorias/{convocatoria_id}/publicar", headers=headers, json=body
    )


def _postular(client, token, **overrides):
    body = {
        "nombres": "Luis",
        "apellidos": "Ramírez",
        "telefono": "987654321",
        "consentimiento_datos": True,
        "canal_origen": "facebook",
        "respuestas": {"¿Tiene carné de sanidad?": "Sí, vigente"},
    }
    body.update(overrides)
    return client.post(f"/api/v1/rrhh/postulaciones/{token}", json=body)


def test_convocatoria_sin_perfil_no_se_publica(env):
    """RN-RRHH-013: sin perfil de puesto aprobado no hay convocatoria."""
    client, ids, _ = env
    h = _token(client)
    convocatoria_id = _crear_convocatoria(client, h, ids, perfil_puesto=None).json()["id"]

    r = _publicar(client, h, convocatoria_id)

    assert r.status_code == 409
    assert "RN-RRHH-013" in r.json()["detail"]


def test_publicar_genera_token_y_cerrar_lo_retira(env):
    client, ids, _ = env
    h = _token(client)
    convocatoria_id = _crear_convocatoria(client, h, ids).json()["id"]

    publicada = _publicar(client, h, convocatoria_id).json()
    assert publicada["estado"] == "publicada"
    assert publicada["token_publico"]

    cerrada = client.post(
        f"/api/v1/rrhh/convocatorias/{convocatoria_id}/cerrar", headers=h
    ).json()
    assert cerrada["estado"] == "cerrada"
    assert cerrada["token_publico"] is None
    # El token retirado ya no recibe postulaciones.
    assert _postular(client, publicada["token_publico"]).status_code == 404


def test_postulacion_publica_sin_jwt_entra_al_tablero(env):
    client, ids, _ = env
    h = _token(client)
    convocatoria_id = _crear_convocatoria(client, h, ids).json()["id"]
    token = _publicar(client, h, convocatoria_id).json()["token_publico"]

    r = _postular(client, token)

    assert r.status_code == 201
    postulante = r.json()
    assert postulante["estado"] == "recibido"
    assert postulante["empresa_id"] == ids["empresa_id"]
    assert postulante["puesto_postulado"] == "Pizzero"
    assert postulante["persona_id"] is None  # el candidato no entra a `persona`
    assert postulante["respuestas"] == {"¿Tiene carné de sanidad?": "Sí, vigente"}


def test_postulacion_sin_consentimiento_rechazada(env):
    """RN-PER-004: sin consentimiento previo no se guardan datos."""
    client, ids, _ = env
    h = _token(client)
    convocatoria_id = _crear_convocatoria(client, h, ids).json()["id"]
    token = _publicar(client, h, convocatoria_id).json()["token_publico"]

    r = _postular(client, token, consentimiento_datos=False)

    assert r.status_code == 409
    assert "RN-PER-004" in r.json()["detail"]


def test_postulacion_con_token_invalido_404(env):
    client, _, _ = env
    assert _postular(client, "token-que-no-existe").status_code == 404


def test_postulacion_fuera_de_fecha_limite_rechazada(env):
    client, ids, _ = env
    h = _token(client)
    convocatoria_id = _crear_convocatoria(
        client, h, ids, fecha_limite="2020-01-01"
    ).json()["id"]
    token = _publicar(client, h, convocatoria_id).json()["token_publico"]

    assert _postular(client, token).status_code == 409


def test_respuestas_demasiado_largas_rechazadas(env):
    """El formulario es de terceros: lo que entra por el endpoint público se
    acota o no se acota nunca."""
    client, ids, _ = env
    h = _token(client)
    convocatoria_id = _crear_convocatoria(client, h, ids).json()["id"]
    token = _publicar(client, h, convocatoria_id).json()["token_publico"]

    r = _postular(client, token, respuestas={"pregunta": "x" * 2001})

    assert r.status_code == 422


def test_avance_por_el_tablero_solo_a_la_columna_siguiente(env):
    client, ids, _ = env
    h = _token(client)
    convocatoria_id = _crear_convocatoria(client, h, ids).json()["id"]
    token = _publicar(client, h, convocatoria_id).json()["token_publico"]
    postulante_id = _postular(client, token).json()["id"]

    salto = client.post(
        f"/api/v1/rrhh/postulantes/{postulante_id}/avanzar",
        headers=h,
        json={"estado": "entrevistado"},
    )
    assert salto.status_code == 409

    siguiente = client.post(
        f"/api/v1/rrhh/postulantes/{postulante_id}/avanzar",
        headers=h,
        json={"estado": "preseleccionado"},
    )
    assert siguiente.status_code == 200
    assert siguiente.json()["estado"] == "preseleccionado"


def test_descartar_exige_motivo_y_queda_registrado(env):
    client, ids, _ = env
    h = _token(client)
    convocatoria_id = _crear_convocatoria(client, h, ids).json()["id"]
    token = _publicar(client, h, convocatoria_id).json()["token_publico"]
    postulante_id = _postular(client, token).json()["id"]

    sin_motivo = client.post(
        f"/api/v1/rrhh/postulantes/{postulante_id}/descartar", headers=h, json={"motivo": ""}
    )
    assert sin_motivo.status_code == 422

    r = client.post(
        f"/api/v1/rrhh/postulantes/{postulante_id}/descartar",
        headers=h,
        json={"motivo": "No tiene disponibilidad para turno noche"},
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "descartado"
    assert r.json()["motivo_descarte"] == "No tiene disponibilidad para turno noche"


def _hasta_oferta(client, h, ids):
    convocatoria_id = _crear_convocatoria(client, h, ids).json()["id"]
    token = _publicar(client, h, convocatoria_id).json()["token_publico"]
    postulante_id = _postular(client, token).json()["id"]
    for etapa in ("preseleccionado", "entrevistado", "verificado", "oferta_enviada"):
        client.post(
            f"/api/v1/rrhh/postulantes/{postulante_id}/avanzar",
            headers=h,
            json={"estado": etapa},
        )
    return convocatoria_id, postulante_id


def test_contratar_crea_persona_y_trabajador(env):
    client, ids, TestSession = env
    h = _token(client)
    _, postulante_id = _hasta_oferta(client, h, ids)

    r = client.post(
        f"/api/v1/rrhh/postulantes/{postulante_id}/contratar",
        headers=h,
        json={
            "cargo": "Pizzero",
            "area": "Cocina",
            "tipo_vinculo": "planilla",
            "fecha_ingreso": "2026-08-15",
            "numero_documento": "70123456",
        },
    )

    assert r.status_code == 201 or r.status_code == 200
    contratado = r.json()
    assert contratado["estado"] == "contratado"
    assert contratado["persona_id"] and contratado["trabajador_id"]

    with TestSession() as s:
        persona = s.get(Persona, __import__("uuid").UUID(contratado["persona_id"]))
        assert persona.nombres == "Luis"
        assert persona.numero_documento == "70123456"


def test_contratar_usa_el_nombre_de_reniec_y_no_el_autodeclarado(env, monkeypatch):
    """Con ese nombre se firma el contrato y se declara a SUNAT, así que no
    puede salir de lo que el postulante escribió de sí mismo en un formulario
    público (RN-PTS-004, mismo criterio que el alta de cliente).

    Lo revisado en pantalla —`nombres`/`apellidos` en el cuerpo— tampoco
    manda sobre RENIEC: prellenar es para **ver** el dato antes de guardar,
    no para pisarlo. Lo enviado se usa solo cuando el proveedor no contesta,
    que es lo que cubre el test de abajo.
    """
    from src.modules.rrhh.application import postulantes as caso_de_uso

    monkeypatch.setattr(
        caso_de_uso, "nombres_desde_dni", lambda dni, n, a: ("PEDRO ANTONIO", "QUISPE MAMANI")
    )
    client, ids, TestSession = env
    h = _token(client)
    _, postulante_id = _hasta_oferta(client, h, ids)

    r = client.post(
        f"/api/v1/rrhh/postulantes/{postulante_id}/contratar",
        headers=h,
        json={
            "cargo": "Pizzero",
            "area": "Cocina",
            "tipo_vinculo": "planilla",
            "fecha_ingreso": "2026-08-15",
            "numero_documento": "70123456",
            "nombres": "Luchito",
            "apellidos": "Tecleado Mal",
        },
    )

    assert r.status_code in (200, 201)
    with TestSession() as s:
        persona = s.get(Persona, __import__("uuid").UUID(r.json()["persona_id"]))
        assert persona.nombres == "PEDRO ANTONIO"
        assert persona.apellidos == "QUISPE MAMANI"


def test_contratar_sin_reniec_usa_lo_revisado_en_pantalla(env, monkeypatch):
    """Factiliza caído o documento que no figura: la contratación **sigue**
    con lo que corrigió quien contrata (ADR-005). Sin esto, un proveedor
    externo caído dejaría a alguien sin poder entrar a planilla."""
    from src.shared.integrations.factiliza import client as factiliza

    def explota(self, dni):
        raise factiliza.FactilizaError("caído")

    monkeypatch.setattr(factiliza.FactilizaClient, "consultar_dni", explota)
    client, ids, TestSession = env
    h = _token(client)
    _, postulante_id = _hasta_oferta(client, h, ids)

    r = client.post(
        f"/api/v1/rrhh/postulantes/{postulante_id}/contratar",
        headers=h,
        json={
            "cargo": "Pizzero",
            "area": "Cocina",
            "tipo_vinculo": "planilla",
            "fecha_ingreso": "2026-08-15",
            "numero_documento": "70123456",
            "nombres": "Luis Alberto",
            "apellidos": "Corregido Aca",
        },
    )

    assert r.status_code in (200, 201)
    with TestSession() as s:
        persona = s.get(Persona, __import__("uuid").UUID(r.json()["persona_id"]))
        assert persona.nombres == "Luis Alberto"
        assert persona.apellidos == "Corregido Aca"


def test_contratar_sin_documento_rechazado(env):
    client, ids, _ = env
    h = _token(client)
    _, postulante_id = _hasta_oferta(client, h, ids)

    r = client.post(
        f"/api/v1/rrhh/postulantes/{postulante_id}/contratar",
        headers=h,
        json={
            "cargo": "Pizzero",
            "area": "Cocina",
            "tipo_vinculo": "planilla",
            "fecha_ingreso": "2026-08-15",
        },
    )

    assert r.status_code == 409


def test_contratado_no_se_descarta(env):
    """Ya contratado, la salida es un cese (RN-RRHH-012), no un descarte."""
    client, ids, _ = env
    h = _token(client)
    _, postulante_id = _hasta_oferta(client, h, ids)
    client.post(
        f"/api/v1/rrhh/postulantes/{postulante_id}/contratar",
        headers=h,
        json={
            "cargo": "Pizzero",
            "area": "Cocina",
            "tipo_vinculo": "planilla",
            "fecha_ingreso": "2026-08-15",
            "numero_documento": "70123457",
        },
    )

    r = client.post(
        f"/api/v1/rrhh/postulantes/{postulante_id}/descartar",
        headers=h,
        json={"motivo": "cambio de opinión"},
    )
    assert r.status_code == 409


def test_induccion_cierra_el_tablero(env):
    client, ids, _ = env
    h = _token(client)
    _, postulante_id = _hasta_oferta(client, h, ids)
    client.post(
        f"/api/v1/rrhh/postulantes/{postulante_id}/contratar",
        headers=h,
        json={
            "cargo": "Pizzero",
            "area": "Cocina",
            "tipo_vinculo": "planilla",
            "fecha_ingreso": "2026-08-15",
            "numero_documento": "70123458",
        },
    )

    for etapa in ("inducido", "confirmado"):
        r = client.post(
            f"/api/v1/rrhh/postulantes/{postulante_id}/avanzar",
            headers=h,
            json={"estado": etapa},
        )
        assert r.status_code == 200
    assert r.json()["estado"] == "confirmado"


def test_tablero_devuelve_las_columnas_en_orden(env):
    client, ids, _ = env
    h = _token(client)
    convocatoria_id = _crear_convocatoria(client, h, ids).json()["id"]
    token = _publicar(client, h, convocatoria_id).json()["token_publico"]
    _postular(client, token)
    _postular(client, token, nombres="Rosa", apellidos="Díaz")

    r = client.get(f"/api/v1/rrhh/convocatorias/{convocatoria_id}/tablero", headers=h)

    assert r.status_code == 200
    columnas = r.json()
    assert [c["estado"] for c in columnas] == [
        "recibido",
        "preseleccionado",
        "entrevistado",
        "verificado",
        "oferta_enviada",
        "contratado",
        "inducido",
        "confirmado",
        "descartado",
    ]
    assert len(columnas[0]["postulantes"]) == 2


def test_rol_sin_permiso_no_gestiona_convocatoria(env):
    client, ids, _ = env
    h = _token(client, "cocinero1", "222222")
    assert _crear_convocatoria(client, h, ids).status_code == 403
