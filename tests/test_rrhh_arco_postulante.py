"""Derechos ARCO sobre `postulante` (Ley 29733): acceso, rectificación,
cancelación por anonimización y purga por plazo de conservación vencido.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.config.settings import settings
from src.core.app import create_app
from src.core.database import Base
from src.modules.rrhh.application.privacidad import purgar_postulantes_vencidos
from src.modules.rrhh.infrastructure.models import Postulante
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import AuditLog, Empresa


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
        ids["empresa_id"] = str(s.scalar(select(Empresa)).id)
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


def _token(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "pin": "123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _postulante(client, headers, ids, **overrides):
    body = {
        "empresa_id": ids["empresa_id"],
        "nombres": "Luis",
        "apellidos": "Ramírez",
        "telefono": "987654321",
        "email": "luis@example.com",
        "puesto_postulado": "Pizzero",
        "fecha_postulacion": "2026-07-01",
        "consentimiento_datos": True,
        "respuestas": {"¿Turno noche?": "Sí"},
    }
    body.update(overrides)
    return client.post("/api/v1/rrhh/postulantes", headers=headers, json=body).json()


def test_acceso_devuelve_la_ficha(env):
    client, ids, _ = env
    h = _token(client)
    postulante_id = _postulante(client, h, ids)["id"]

    r = client.get(f"/api/v1/rrhh/postulantes/{postulante_id}", headers=h)

    assert r.status_code == 200
    assert r.json()["nombres"] == "Luis"


def test_rectificacion_corrige_contacto(env):
    client, ids, _ = env
    h = _token(client)
    postulante_id = _postulante(client, h, ids)["id"]

    r = client.patch(
        f"/api/v1/rrhh/postulantes/{postulante_id}",
        headers=h,
        json={"telefono": "911111111"},
    )

    assert r.status_code == 200
    assert r.json()["telefono"] == "911111111"
    assert r.json()["nombres"] == "Luis"  # lo no enviado no se toca


def test_cancelacion_anonimiza_y_conserva_la_evidencia(env):
    client, ids, _ = env
    h = _token(client)
    creado = _postulante(client, h, ids)
    client.post(
        f"/api/v1/rrhh/postulantes/{creado['id']}/descartar",
        headers=h,
        json={"motivo": "Sin disponibilidad para turno noche"},
    )

    r = client.post(
        f"/api/v1/rrhh/postulantes/{creado['id']}/anonimizar",
        headers=h,
        json={"motivo": "solicitud del titular"},
    )

    assert r.status_code == 200
    ficha = r.json()
    assert ficha["nombres"] == "ANONIMIZADO"
    assert ficha["telefono"] is None
    assert ficha["email"] is None
    assert ficha["respuestas"] is None
    assert ficha["anonimizado_at"] is not None
    # Lo que sustenta la decisión sobrevive: no es dato identificable.
    assert ficha["motivo_descarte"] == "Sin disponibilidad para turno noche"
    assert ficha["puesto_postulado"] == "Pizzero"


def test_anonimizar_deja_rastro_sin_guardar_la_pii(env):
    client, ids, TestSession = env
    h = _token(client)
    postulante_id = _postulante(client, h, ids)["id"]

    client.post(
        f"/api/v1/rrhh/postulantes/{postulante_id}/anonimizar",
        headers=h,
        json={"motivo": "solicitud del titular"},
    )

    with TestSession() as s:
        entrada = s.scalar(select(AuditLog).where(AuditLog.entidad == "postulante"))
        assert entrada.accion == "anonimizar"
        assert "nombres" in entrada.datos_despues["campos_anonimizados"]
        # El valor borrado NUNCA se guarda: si estuviera acá, la
        # anonimización no serviría de nada.
        assert "Luis" not in str(entrada.datos_despues)


def test_anonimizar_dos_veces_409(env):
    client, ids, _ = env
    h = _token(client)
    postulante_id = _postulante(client, h, ids)["id"]
    url = f"/api/v1/rrhh/postulantes/{postulante_id}/anonimizar"
    body = {"motivo": "solicitud del titular"}

    assert client.post(url, headers=h, json=body).status_code == 200
    assert client.post(url, headers=h, json=body).status_code == 409


def test_rectificar_anonimizado_409(env):
    client, ids, _ = env
    h = _token(client)
    postulante_id = _postulante(client, h, ids)["id"]
    client.post(
        f"/api/v1/rrhh/postulantes/{postulante_id}/anonimizar",
        headers=h,
        json={"motivo": "solicitud del titular"},
    )

    r = client.patch(
        f"/api/v1/rrhh/postulantes/{postulante_id}",
        headers=h,
        json={"telefono": "911111111"},
    )
    assert r.status_code == 409


def test_contratado_no_se_anonimiza_por_aca(env):
    """Ya es trabajador: sus datos viven en `persona` y bajo retención
    laboral; su ARCO se ejerce allá."""
    client, ids, _ = env
    h = _token(client)
    postulante_id = _postulante(client, h, ids)["id"]
    for etapa in ("preseleccionado", "entrevistado", "verificado", "oferta_enviada"):
        client.post(
            f"/api/v1/rrhh/postulantes/{postulante_id}/avanzar",
            headers=h,
            json={"estado": etapa},
        )
    client.post(
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

    r = client.post(
        f"/api/v1/rrhh/postulantes/{postulante_id}/anonimizar",
        headers=h,
        json={"motivo": "solicitud del titular"},
    )
    assert r.status_code == 409


def test_plazo_de_conservacion_se_declara_solo(env):
    """Sin plazo la ficha sería inpurgable y el aviso de privacidad
    prometería algo que nadie aplica."""
    client, ids, _ = env
    h = _token(client)

    creado = _postulante(client, h, ids)

    esperado = date(2026, 7, 1)
    meses = settings.rrhh_plazo_conservacion_postulante_meses
    esperado = esperado.replace(year=esperado.year + meses // 12)
    assert creado["plazo_conservacion_declarado"] == esperado.isoformat()


def test_purga_anonimiza_lo_vencido_y_respeta_lo_vigente(env):
    client, ids, TestSession = env
    h = _token(client)
    hoy = date(2026, 8, 1)
    vencido = _postulante(
        client, h, ids, nombres="Vencido", plazo_conservacion_declarado="2026-07-31"
    )
    vigente = _postulante(
        client, h, ids, nombres="Vigente", plazo_conservacion_declarado="2027-01-01"
    )

    with TestSession() as s:
        purgados = purgar_postulantes_vencidos(s, hoy)
        s.commit()

    assert purgados == 1
    with TestSession() as s:
        import uuid as _uuid

        assert s.get(Postulante, _uuid.UUID(vencido["id"])).nombres == "ANONIMIZADO"
        assert s.get(Postulante, _uuid.UUID(vigente["id"])).nombres == "Vigente"


def test_purga_no_toca_al_contratado(env):
    """El plazo del postulante no manda sobre datos bajo retención laboral."""
    client, ids, TestSession = env
    h = _token(client)
    postulante_id = _postulante(
        client, h, ids, plazo_conservacion_declarado="2026-07-31"
    )["id"]
    for etapa in ("preseleccionado", "entrevistado", "verificado", "oferta_enviada"):
        client.post(
            f"/api/v1/rrhh/postulantes/{postulante_id}/avanzar",
            headers=h,
            json={"estado": etapa},
        )
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

    with TestSession() as s:
        assert purgar_postulantes_vencidos(s, date(2026, 8, 1)) == 0


def test_sumar_meses_no_desborda_el_mes_corto():
    from src.modules.rrhh.domain.rules import sumar_meses

    assert sumar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert sumar_meses(date(2026, 12, 15), 12) == date(2027, 12, 15)
    assert sumar_meses(date(2026, 3, 1), 0) == date(2026, 3, 1)


def test_timedelta_no_se_usa_para_meses():
    """Guardia del atajo tentador: 12 meses no son 365 días en año bisiesto."""
    from src.modules.rrhh.domain.rules import sumar_meses

    assert sumar_meses(date(2024, 1, 1), 12) != date(2024, 1, 1) + timedelta(days=365)
