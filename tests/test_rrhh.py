"""Tests del slice rrhh: ciclo laboral completo. SQLite en memoria +
override de get_db, mismo patrón que test_purchases.py.
"""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.app import create_app
from src.core.database import Base
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Empresa,
    Persona,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
)
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
        sucursal = s.scalar(select(Sucursal))
        admin = s.scalar(select(Usuario).where(Usuario.username == "admin"))
        persona = Persona(
            nombres="Ana", apellidos="Torres", tipo_documento="dni", numero_documento="20000001"
        )
        s.add(persona)
        s.flush()

        cocinero = Usuario(username="cocinero1", pin_hash=hash_pin("222222"), tipo="humano")
        s.add(cocinero)
        s.flush()
        rol_cocinero = s.scalar(select(Rol).where(Rol.nombre == "cocinero"))
        s.add(UsuarioRol(usuario_id=cocinero.id, rol_id=rol_cocinero.id))

        ids.update(
            empresa_id=str(empresa.id),
            sucursal_id=str(sucursal.id),
            marca_id=str(sucursal.marca_id),
            grupo_id=str(empresa.grupo_id),
            admin_usuario_id=str(admin.id),
            persona_id=str(persona.id),
            cocinero_usuario_id=str(cocinero.id),
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
        yield c, ids, TestSession


def _token(client, username="admin", pin="123456"):
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _crear_trabajador(client, headers, ids, persona_id=None, **overrides):
    body = {
        "empresa_id": ids["empresa_id"],
        "persona_id": persona_id or ids["persona_id"],
        "cargo": "Mozo",
        "area": "Salón",
        "tipo_vinculo": "planilla",
        "fecha_ingreso": "2026-01-01",
    }
    body.update(overrides)
    return client.post("/api/v1/rrhh/trabajadores", headers=headers, json=body)


def test_crear_trabajador_planilla(env):
    client, ids, _ = env
    h = _token(client)
    r = _crear_trabajador(client, h, ids)
    assert r.status_code == 201
    assert r.json()["registra_asistencia"] is True


# --- Centro de labores (ADR-062, RN-RRHH-019) --------------------------------
def _sucursal_ajena(TestSession, ids):
    """Sucursal de OTRA empresa del mismo grupo: el caso que la regla ataja."""
    with TestSession() as s:
        otra = Empresa(
            grupo_id=uuid.UUID(ids["grupo_id"]),
            razon_social="Otra SAC",
            ruc="20999999991",
            domicilio_fiscal="Av. Otra 100",
            tipo="operativa",
        )
        s.add(otra)
        s.flush()
        sucursal = Sucursal(
            marca_id=uuid.UUID(ids["marca_id"]),
            empresa_id=otra.id,
            nombre="Local ajeno",
            direccion="Av. Otra 100",
            tenencia="alquilada",
        )
        s.add(sucursal)
        s.commit()
        return str(sucursal.id)


def test_trabajador_se_asigna_a_su_sucursal(env):
    client, ids, _ = env
    h = _token(client)
    r = _crear_trabajador(client, h, ids, sucursal_id=ids["sucursal_id"])
    assert r.status_code == 201
    assert r.json()["sucursal_id"] == ids["sucursal_id"]


def test_trabajador_sin_sucursal_es_valido(env):
    """Gerencia y administración no están en ningún local."""
    client, ids, _ = env
    r = _crear_trabajador(client, _token(client), ids)
    assert r.status_code == 201
    assert r.json()["sucursal_id"] is None


def test_no_se_asigna_a_sucursal_de_otra_empresa(env):
    client, ids, TestSession = env
    h = _token(client)
    ajena = _sucursal_ajena(TestSession, ids)

    r = _crear_trabajador(client, h, ids, sucursal_id=ajena)
    assert r.status_code == 409
    assert "RN-RRHH-019" in r.json()["detail"]

    trabajador_id = _crear_trabajador(client, h, ids).json()["id"]
    patch = client.patch(
        f"/api/v1/rrhh/trabajadores/{trabajador_id}",
        headers=h,
        json={"sucursal_id": ajena},
    )
    assert patch.status_code == 409


def test_patch_cambia_y_borra_el_centro_de_labores(env):
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids).json()["id"]
    url = f"/api/v1/rrhh/trabajadores/{trabajador_id}"

    asignar = client.patch(url, headers=h, json={"sucursal_id": ids["sucursal_id"]})
    assert asignar.status_code == 200
    assert asignar.json()["sucursal_id"] == ids["sucursal_id"]

    # Un PATCH de otro campo no puede tirar abajo la sucursal ya asignada.
    otro = client.patch(url, headers=h, json={"cargo": "Cajero"})
    assert otro.json()["sucursal_id"] == ids["sucursal_id"]

    # `null` explícito sí la borra: quedarse sin local es un estado válido.
    borrar = client.patch(url, headers=h, json={"sucursal_id": None})
    assert borrar.status_code == 200
    assert borrar.json()["sucursal_id"] is None


def test_locacion_servicios_fuerza_no_registra_asistencia(env):
    client, ids, _ = env
    h = _token(client)
    r = _crear_trabajador(
        client, h, ids, tipo_vinculo="locacion_servicios", registra_asistencia=True
    )
    assert r.status_code == 201
    assert r.json()["registra_asistencia"] is False


def test_rol_sin_permiso_rrhh_403(env):
    client, ids, _ = env
    h = _token(client, "cocinero1", "222222")
    r = _crear_trabajador(client, h, ids)
    assert r.status_code == 403


def test_flujo_contrato_laboral_crear_firmar(env):
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids).json()["id"]

    oc = client.post(
        "/api/v1/rrhh/contratos-laborales",
        headers=h,
        json={
            "trabajador_id": trabajador_id,
            "modalidad": "indeterminado",
            "jornada_horas_semana": "48",
            "remuneracion": "1300",
            "fecha_inicio": "2026-01-01",
        },
    )
    assert oc.status_code == 201
    assert oc.json()["estado"] == "borrador"
    contrato_id = oc.json()["id"]

    firmar = client.post(
        f"/api/v1/rrhh/contratos-laborales/{contrato_id}/firmar",
        headers=h,
        json={"fecha_firma": "2026-01-01"},
    )
    assert firmar.status_code == 200
    assert firmar.json()["estado"] == "firmado"

    firmar_de_nuevo = client.post(
        f"/api/v1/rrhh/contratos-laborales/{contrato_id}/firmar",
        headers=h,
        json={"fecha_firma": "2026-01-02"},
    )
    assert firmar_de_nuevo.status_code == 409


def test_contrato_plazo_fijo_sin_fecha_fin_409(env):
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids).json()["id"]
    r = client.post(
        "/api/v1/rrhh/contratos-laborales",
        headers=h,
        json={
            "trabajador_id": trabajador_id,
            "modalidad": "modal_temporada",
            "jornada_horas_semana": "40",
            "remuneracion": "1200",
            "fecha_inicio": "2026-01-01",
        },
    )
    assert r.status_code == 409


def _postulante_manual(client, headers, ids, **overrides):
    """Carga manual (referido o CV en mano), sin pasar por el formulario."""
    body = {
        "empresa_id": ids["empresa_id"],
        "nombres": "Ana",
        "apellidos": "Torres",
        "puesto_postulado": "Cajero",
        "fecha_postulacion": "2026-07-01",
        "consentimiento_datos": True,
    }
    body.update(overrides)
    return client.post("/api/v1/rrhh/postulantes", headers=headers, json=body)


def test_postulante_sin_consentimiento_409(env):
    client, ids, _ = env
    h = _token(client)
    r = _postulante_manual(client, h, ids, consentimiento_datos=False)
    assert r.status_code == 409


def test_postulante_con_consentimiento_201(env):
    client, ids, _ = env
    h = _token(client)
    r = _postulante_manual(client, h, ids)
    assert r.status_code == 201
    assert r.json()["estado"] == "recibido"
    # El candidato no entra a `persona` por postular.
    assert r.json()["persona_id"] is None


def test_flujo_solicitud_permiso_crear_aprobar(env):
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids).json()["id"]

    r = client.post(
        "/api/v1/rrhh/solicitudes-permiso",
        headers=h,
        json={
            "trabajador_id": trabajador_id,
            "tipo": "vacaciones",
            "fecha_desde": "2026-08-01",
            "fecha_hasta": "2026-08-15",
        },
    )
    assert r.status_code == 201
    solicitud_id = r.json()["id"]
    assert r.json()["estado"] == "pendiente"

    aprobar = client.post(
        f"/api/v1/rrhh/solicitudes-permiso/{solicitud_id}/aprobar", headers=h
    )
    assert aprobar.status_code == 200
    assert aprobar.json()["estado"] == "aprobada"

    aprobar_de_nuevo = client.post(
        f"/api/v1/rrhh/solicitudes-permiso/{solicitud_id}/aprobar", headers=h
    )
    assert aprobar_de_nuevo.status_code == 409


def test_solicitud_permiso_horas_sin_horas_409(env):
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids).json()["id"]
    r = client.post(
        "/api/v1/rrhh/solicitudes-permiso",
        headers=h,
        json={"trabajador_id": trabajador_id, "tipo": "permiso_horas", "fecha_desde": "2026-08-01"},
    )
    assert r.status_code == 409


def test_flujo_asistencia_marcar_entrada_salida(env):
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids).json()["id"]

    entrada = client.post(
        "/api/v1/rrhh/asistencia/entrada",
        headers=h,
        json={"trabajador_id": trabajador_id, "fecha": "2026-08-01", "hora_entrada": "09:00:00"},
    )
    assert entrada.status_code == 201

    salida = client.post(
        "/api/v1/rrhh/asistencia/salida",
        headers=h,
        json={"trabajador_id": trabajador_id, "fecha": "2026-08-01", "hora_salida": "18:00:00"},
    )
    assert salida.status_code == 200
    assert salida.json()["hora_entrada"] == "09:00:00"


def test_asistencia_bloqueada_para_locacion_servicios(env):
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(
        client, h, ids, tipo_vinculo="locacion_servicios"
    ).json()["id"]

    r = client.post(
        "/api/v1/rrhh/asistencia/entrada",
        headers=h,
        json={"trabajador_id": trabajador_id, "fecha": "2026-08-01", "hora_entrada": "09:00:00"},
    )
    assert r.status_code == 409


def test_idempotencia_boleta_pago(env):
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids).json()["id"]

    body = {
        "trabajador_id": trabajador_id,
        "periodo": "2026-07",
        "dias_laborados": 30,
        "remuneracion": "1300.00",
        "ingresos": {"basico": "1300.00"},
        "descuentos": {"onp": "169.00"},
        "aportes_empleador": "117.00",
        "neto_pagar": "1131.00",
        "fecha_pago": "2026-08-03",
        "idempotency_key": "boleta-2026-07-1",
    }
    r1 = client.post("/api/v1/rrhh/boletas-pago", headers=h, json=body)
    r2 = client.post("/api/v1/rrhh/boletas-pago", headers=h, json=body)
    assert r1.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def test_cese_y_liquidacion_bss(env):
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids).json()["id"]

    cese = client.post(
        f"/api/v1/rrhh/trabajadores/{trabajador_id}/cesar",
        headers=h,
        json={"fecha_cese": "2026-08-01"},
    )
    assert cese.status_code == 200
    assert cese.json()["estado"] == "cesado"

    liquidacion = client.post(
        "/api/v1/rrhh/liquidaciones-bss",
        headers=h,
        json={
            "trabajador_id": trabajador_id,
            "cts_pendiente": "500.00",
            "vacaciones_truncas": "300.00",
            "fecha_pago": "2026-08-02",
            "idempotency_key": "liq-key-1",
        },
    )
    assert liquidacion.status_code == 201
    assert Decimal(liquidacion.json()["total"]) == Decimal("800.00")
    assert liquidacion.json()["dentro_de_plazo"] is True


def test_emitir_memorandum_amonestacion_acta_certificado(env):
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids).json()["id"]

    memo = client.post(
        "/api/v1/rrhh/memorandums",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "emisor_id": ids["admin_usuario_id"],
            "asunto": "Tardanza",
            "cuerpo": "Se le recuerda cumplir el horario.",
            "fecha": "2026-08-01",
            "destinatario_trabajador_id": trabajador_id,
        },
    )
    assert memo.status_code == 201

    amonestacion = client.post(
        "/api/v1/rrhh/amonestaciones",
        headers=h,
        json={
            "trabajador_id": trabajador_id,
            "tipo": "escrita",
            "falta": "Tardanza reiterada",
            "fecha_hecho": "2026-07-30",
            "fecha_emision": "2026-08-01",
            "emisor_id": ids["admin_usuario_id"],
        },
    )
    assert amonestacion.status_code == 201

    acta = client.post(
        "/api/v1/rrhh/actas",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "tipo": "incidente",
            "fecha": "2026-08-01",
            "lugar": "Local Central",
            "hechos": "Se constató el hecho.",
            "participantes": [{"nombre": "Ana Torres", "firma": True}],
        },
    )
    assert acta.status_code == 201

    certificado = client.post(
        "/api/v1/rrhh/certificados-trabajo",
        headers=h,
        json={
            "trabajador_id": trabajador_id,
            "fecha_emision": "2026-08-01",
            "cargos": "Mozo",
        },
    )
    assert certificado.status_code == 201
    assert certificado.json()["tiempo_servicios_meses"] >= 0


def test_pacto_permanencia(env):
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids).json()["id"]

    r = client.post(
        "/api/v1/rrhh/pactos-permanencia",
        headers=h,
        json={
            "trabajador_id": trabajador_id,
            "capacitacion_descripcion": "Curso de repostería avanzada",
            "capacitacion_tipo": "curso",
            "costo_financiado": "3000.00",
            "plazo_permanencia_meses": 12,
            "fecha_inicio": "2026-08-01",
            "fecha_fin_compromiso": "2027-08-01",
        },
    )
    assert r.status_code == 201
    assert Decimal(r.json()["costo_financiado"]) == Decimal("3000.00")


def test_crear_socio(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post(
        "/api/v1/rrhh/socios",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "persona_id": ids["persona_id"],
            "porcentaje_participacion": "25.00",
        },
    )
    assert r.status_code == 201


def test_socio_sin_grupo_ni_empresa_409(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post(
        "/api/v1/rrhh/socios",
        headers=h,
        json={"persona_id": ids["persona_id"], "porcentaje_participacion": "25.00"},
    )
    assert r.status_code == 409


# --- Cuenta derivada por persona (ADR-070): guarda contra duplicar filas ---
def test_listar_trabajadores_no_duplica_por_recontratacion(env):
    """`trabajador.usuario_id` es una subconsulta (`column_property`), no un
    `relationship` con eager load: con dos filas trabajador sobre una misma
    persona (recontratación), un JOIN mal armado duplicaría la fila padre en
    silencio y `total` dejaría de coincidir con `len(items)`."""
    client, ids, _ = env
    h = _token(client)
    primero = _crear_trabajador(client, h, ids).json()
    client.post(
        f"/api/v1/rrhh/trabajadores/{primero['id']}/cesar",
        headers=h,
        json={"fecha_cese": "2026-02-01"},
    )
    _crear_trabajador(client, h, ids, fecha_ingreso="2026-03-01")

    r = client.get("/api/v1/rrhh/trabajadores", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == len(body["items"])
    assert body["total"] == 2


def test_nombres_por_usuario_prioriza_al_trabajador_activo(env):
    """Ranking de ventas (ADR-070): una persona recontratada tiene dos filas
    `trabajador` compartiendo la misma cuenta — el cargo mostrado tiene que
    ser el del puesto vigente, no el viejo."""
    from src.modules.rrhh.application.queries_publicas import nombres_por_usuario

    client, ids, TestSession = env
    h = _token(client)
    cuenta_id = ids["cocinero_usuario_id"]
    assert (
        client.patch(
            f"/api/v1/users/{cuenta_id}",
            headers=h,
            json={"persona_id": ids["persona_id"]},
        ).status_code
        == 200
    )
    viejo = _crear_trabajador(client, h, ids, cargo="Ayudante de cocina").json()
    client.post(
        f"/api/v1/rrhh/trabajadores/{viejo['id']}/cesar",
        headers=h,
        json={"fecha_cese": "2026-02-01"},
    )
    _crear_trabajador(
        client, h, ids, cargo="Jefe de cocina", fecha_ingreso="2026-03-01"
    )

    with TestSession() as s:
        resultado = nombres_por_usuario(s, [uuid.UUID(cuenta_id)])
    assert resultado[uuid.UUID(cuenta_id)]["cargo"] == "Jefe de cocina"
