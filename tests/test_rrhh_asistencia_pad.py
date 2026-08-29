"""Turno de trabajo y pad de marcación del local (ADR-064, ADR-065).

SQLite en memoria + override de `get_db`, mismo patrón que `test_rrhh.py`.
"""

import base64
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.app import create_app
from src.core.database import Base
from src.modules.rrhh.application import avisos_asistencia, turnos
from src.modules.rrhh.application import terminales as terminales_uc
from src.modules.rrhh.infrastructure.models import Asistencia, TurnoSucursal
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Empresa,
    Notificacion,
    Persona,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin
from src.shared.ubicacion import metros_entre

LIMA = ZoneInfo("America/Lima")
PIN_TRABAJADOR = "222222"


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

        persona = Persona(
            nombres="Ana",
            apellidos="Torres",
            tipo_documento="dni",
            numero_documento="20000001",
        )
        s.add(persona)
        s.flush()

        # El trabajador que marca: tiene usuario con PIN, que es su firma.
        # La cuenta se liga por `persona_id` (ADR-070) — es la misma arista
        # que la pantalla de Usuarios usa para vincular «Persona vinculada»,
        # no una columna aparte en `trabajador`.
        cocinero = Usuario(
            username="cocinero1",
            pin_hash=hash_pin(PIN_TRABAJADOR),
            tipo="humano",
            persona_id=persona.id,
        )
        s.add(cocinero)
        s.flush()

        # La cuenta de servicio de la tablet: un permiso y nada más.
        terminal = Usuario(
            username="pad-castilla", pin_hash=hash_pin("999999"), tipo="humano"
        )
        s.add(terminal)
        s.flush()
        rol_terminal = s.scalar(select(Rol).where(Rol.nombre == "terminal_asistencia"))
        s.add(UsuarioRol(usuario_id=terminal.id, rol_id=rol_terminal.id))
        s.add(UsuarioSucursal(usuario_id=terminal.id, sucursal_id=sucursal.id))

        # El terminal enrolado (ADR-079): sin este secreto en `X-Terminal`,
        # el pad no marca — de acá en más, mismo tratamiento que el PIN.
        _, codigo = terminales_uc.crear(s, sucursal_id=sucursal.id, nombre="Pasillo")
        secreto_terminal = terminales_uc.enrolar(s, sucursal_id=sucursal.id, codigo=codigo)

        ids.update(
            empresa_id=str(empresa.id),
            sucursal_id=str(sucursal.id),
            grupo_id=str(empresa.grupo_id),
            persona_id=str(persona.id),
            usuario_trabajador_id=str(cocinero.id),
            terminal_secreto=secreto_terminal,
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


def _crear_trabajador(client, headers, ids, **overrides):
    body = {
        "empresa_id": ids["empresa_id"],
        "persona_id": ids["persona_id"],
        "cargo": "Cocinero",
        "area": "Cocina",
        "tipo_vinculo": "planilla",
        "fecha_ingreso": "2026-01-01",
        "sucursal_id": ids["sucursal_id"],
    }
    body.update(overrides)
    r = client.post("/api/v1/rrhh/trabajadores", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _vincular_persona(client, headers, usuario_id, persona_id):
    """La cuenta se vincula desde Usuarios (ADR-070), no desde el trabajador."""
    return client.patch(
        f"/api/v1/users/{usuario_id}", headers=headers, json={"persona_id": persona_id}
    )


def _crear_turno(client, headers, ids, **overrides):
    body = {
        "sucursal_id": ids["sucursal_id"],
        "nombre": "Mañana",
        "hora_inicio": "09:00:00",
        "hora_fin": "17:00:00",
        "hora_limite_salida": "18:00:00",
        "tolerancia_min": 5,
    }
    body.update(overrides)
    return client.post("/api/v1/rrhh/turnos", headers=headers, json=body)


def _tarjetas(client, headers, ids):
    return client.get(
        f"/api/v1/rrhh/asistencia/terminal/tarjetas?sucursal_id={ids['sucursal_id']}",
        headers=headers,
    )


def _marcar(
    client,
    headers,
    ids,
    trabajador_id,
    pin=PIN_TRABAJADOR,
    terminal=True,
    **evidencia,
):
    """`terminal=True` manda el secreto del terminal ya enrolado en `env`
    (mismo terminal para todos los tests que no lo pongan a prueba); `**
    evidencia` deja pasar `foto`/`lat`/`lng` sueltos."""
    h = dict(headers)
    if terminal:
        h["X-Terminal"] = ids["terminal_secreto"]
    return client.post(
        f"/api/v1/rrhh/asistencia/terminal/marcar?sucursal_id={ids['sucursal_id']}",
        headers=h,
        json={"trabajador_id": trabajador_id, "pin": pin, **evidencia},
    )


# --- Turnos ---------------------------------------------------------------------
def test_crear_turno_y_no_repetir_nombre(env):
    client, ids, _ = env
    h = _token(client)
    assert _crear_turno(client, h, ids).status_code == 201
    assert _crear_turno(client, h, ids).status_code == 409


def test_turno_vigente_elige_el_que_empieza_mas_cerca(env):
    """El cambio de turno siempre se pisa: quien marca a las 15:05 entra al
    turno de las 15:00, no al de la mañana que todavía no terminó."""
    client, ids, TestSession = env
    h = _token(client)
    _crear_turno(client, h, ids)
    _crear_turno(
        client,
        h,
        ids,
        nombre="Tarde",
        hora_inicio="15:00:00",
        hora_fin="23:00:00",
        hora_limite_salida="23:30:00",
    )

    with TestSession() as s:
        momento = datetime(2026, 8, 24, 15, 5, tzinfo=LIMA)
        turno = turnos.turno_vigente(s, uuid.UUID(ids["sucursal_id"]), momento)
        assert turno is not None and turno.nombre == "Tarde"


def test_turno_de_noche_cruza_la_medianoche(env):
    client, ids, TestSession = env
    h = _token(client)
    _crear_turno(
        client,
        h,
        ids,
        nombre="Noche",
        hora_inicio="22:00:00",
        hora_fin="04:00:00",
        hora_limite_salida="04:30:00",
    )
    with TestSession() as s:
        sucursal_id = uuid.UUID(ids["sucursal_id"])
        de_madrugada = datetime(2026, 8, 25, 2, 0, tzinfo=LIMA)
        assert turnos.turno_vigente(s, sucursal_id, de_madrugada).nombre == "Noche"
        de_tarde = datetime(2026, 8, 24, 14, 0, tzinfo=LIMA)
        assert turnos.turno_vigente(s, sucursal_id, de_tarde) is None


def test_tardanza_respeta_la_tolerancia():
    turno = TurnoSucursal(
        nombre="Mañana",
        hora_inicio=time(9, 0),
        hora_fin=time(17, 0),
        tolerancia_min=5,
        hora_limite_salida=time(18, 0),
    )
    assert turnos.tardanza_de(turno, datetime(2026, 8, 24, 9, 4, tzinfo=LIMA)) == 0
    assert turnos.tardanza_de(turno, datetime(2026, 8, 24, 9, 20, tzinfo=LIMA)) == 15
    # Llegar antes no es tardanza negativa.
    assert turnos.tardanza_de(turno, datetime(2026, 8, 24, 8, 50, tzinfo=LIMA)) == 0
    assert turnos.tardanza_de(None, datetime(2026, 8, 24, 9, 20, tzinfo=LIMA)) == 0


# --- Pad ------------------------------------------------------------------------
def test_el_pad_marca_entrada_y_despues_salida(env):
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids)
    _crear_turno(client, h, ids)
    hterm = _token(client, "pad-castilla", "999999")

    entrada = _marcar(client, hterm, ids, trabajador_id)
    assert entrada.status_code == 200, entrada.text
    assert entrada.json()["tipo"] == "entrada"

    salida = _marcar(client, hterm, ids, trabajador_id)
    assert salida.json()["tipo"] == "salida"
    # Quedarse de más nunca genera horas extra (RN-RRHH-022).
    assert Decimal(salida.json()["asistencia"]["horas_extra"]) == 0

    # Un tercer toque no vuelve a pisar la hora de salida.
    assert _marcar(client, hterm, ids, trabajador_id).status_code == 409


def test_las_tarjetas_muestran_solo_el_nombre_y_el_estado(env):
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids)
    hterm = _token(client, "pad-castilla", "999999")

    r = _tarjetas(client, hterm, ids)
    assert r.status_code == 200
    tarjeta = r.json()[0]
    assert tarjeta["nombre"] == "Ana Torres"
    assert tarjeta["marco_entrada"] is False
    assert set(tarjeta) == {"trabajador_id", "nombre", "marco_entrada", "marco_salida"}

    _marcar(client, hterm, ids, trabajador_id)
    assert _tarjetas(client, hterm, ids).json()[0]["marco_entrada"] is True


def test_pin_equivocado_no_marca_y_bloquea_a_los_cinco(env):
    client, ids, TestSession = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids)
    hterm = _token(client, "pad-castilla", "999999")

    for _ in range(4):
        r = _marcar(client, hterm, ids, trabajador_id, pin="000000")
        assert r.status_code == 401
    # El quinto intento cruza el tope del lockout compartido con el login.
    assert _marcar(client, hterm, ids, trabajador_id, pin="000000").status_code == 423
    # Y con el PIN correcto tampoco entra mientras dure el bloqueo.
    assert _marcar(client, hterm, ids, trabajador_id).status_code == 423

    with TestSession() as s:
        assert s.scalar(select(Asistencia)) is None


def test_el_pad_no_marca_por_gente_de_otro_local(env):
    client, ids, TestSession = env
    h = _token(client)
    with TestSession() as s:
        primera = s.scalar(select(Sucursal))
        otra = Sucursal(
            empresa_id=uuid.UUID(ids["empresa_id"]),
            marca_id=primera.marca_id,
            nombre="Otra",
            direccion="Av. Otra 1",
            tenencia="alquilada",
        )
        s.add(otra)
        s.commit()
        otra_id = str(otra.id)

    trabajador_id = _crear_trabajador(client, h, ids, sucursal_id=otra_id)
    hterm = _token(client, "pad-castilla", "999999")
    assert _marcar(client, hterm, ids, trabajador_id).status_code == 403


def test_sin_usuario_no_hay_firma(env):
    client, ids, _ = env
    h = _token(client)
    # Desvincular la cuenta de la persona: el trabajador queda sin firma.
    assert _vincular_persona(client, h, ids["usuario_trabajador_id"], None).status_code == 200
    trabajador_id = _crear_trabajador(client, h, ids)
    hterm = _token(client, "pad-castilla", "999999")
    r = _marcar(client, hterm, ids, trabajador_id)
    assert r.status_code == 409
    assert "PIN" in r.json()["detail"]


def test_asignarle_la_cuenta_despues_lo_habilita_a_marcar(env):
    """El bug reportado: vincular la persona desde Usuarios tiene que
    habilitar el pad EN EL ACTO — antes el pad solo leía
    `trabajador.usuario_id`, una columna aparte que esta pantalla nunca
    tocaba, así que el vínculo quedaba guardado pero sin efecto (ADR-070)."""
    client, ids, _ = env
    h = _token(client)
    assert _vincular_persona(client, h, ids["usuario_trabajador_id"], None).status_code == 200
    trabajador_id = _crear_trabajador(client, h, ids)
    _crear_turno(client, h, ids)
    hterm = _token(client, "pad-castilla", "999999")
    assert _marcar(client, hterm, ids, trabajador_id).status_code == 409

    r = _vincular_persona(client, h, ids["usuario_trabajador_id"], ids["persona_id"])
    assert r.status_code == 200, r.text
    assert r.json()["persona_id"] == ids["persona_id"]

    r = client.get(f"/api/v1/rrhh/trabajadores/{trabajador_id}", headers=h)
    assert r.json()["usuario_id"] == ids["usuario_trabajador_id"]
    assert _marcar(client, hterm, ids, trabajador_id).status_code == 200


def test_quitarle_la_cuenta_lo_deja_sin_marcar(env):
    """`persona_id: null` explícito desvincula: quien dejó de usar su acceso
    vuelve a marcar por back-office. Omitir el campo, en cambio, no lo toca."""
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids)

    r = client.get(f"/api/v1/rrhh/trabajadores/{trabajador_id}", headers=h)
    assert r.json()["usuario_id"] == ids["usuario_trabajador_id"]

    r = _vincular_persona(client, h, ids["usuario_trabajador_id"], None)
    assert r.status_code == 200, r.text
    assert r.json()["persona_id"] is None

    r = client.get(f"/api/v1/rrhh/trabajadores/{trabajador_id}", headers=h)
    assert r.json()["usuario_id"] is None


def test_persona_recontratada_comparte_cuenta_entre_las_dos_fichas(env):
    """Recontratación: una persona con dos filas `trabajador` (la cesada y la
    activa) comparten la misma cuenta — a diferencia de antes (una cuenta,
    un `trabajador.usuario_id`), ahora es correcto que las dos fichas
    resuelvan al mismo `usuario_id` (ADR-070)."""
    client, ids, TestSession = env
    h = _token(client)
    primero_id = _crear_trabajador(client, h, ids)
    r = client.post(
        f"/api/v1/rrhh/trabajadores/{primero_id}/cesar",
        headers=h,
        json={"fecha_cese": "2026-02-01"},
    )
    assert r.status_code == 200, r.text

    segundo_id = _crear_trabajador(client, h, ids, fecha_ingreso="2026-03-01")

    r1 = client.get(f"/api/v1/rrhh/trabajadores/{primero_id}", headers=h)
    r2 = client.get(f"/api/v1/rrhh/trabajadores/{segundo_id}", headers=h)
    assert r1.json()["usuario_id"] == ids["usuario_trabajador_id"]
    assert r2.json()["usuario_id"] == ids["usuario_trabajador_id"]

    hterm = _token(client, "pad-castilla", "999999")
    assert _marcar(client, hterm, ids, segundo_id).status_code == 200


def test_dos_cuentas_no_se_ligan_a_la_misma_persona(env):
    """El pad resuelve una sola cuenta por persona: si dos cuentas pudieran
    apuntar a la misma persona, no sabría con cuál PIN firmar."""
    client, ids, _ = env
    h = _token(client)
    r = client.post(
        "/api/v1/users",
        headers=h,
        json={"username": "cocinero2", "pin": "333333", "persona_id": ids["persona_id"]},
    )
    assert r.status_code == 409, r.text
    assert "cocinero1" in r.json()["detail"]


def test_la_cuenta_del_pad_no_se_liga_a_una_persona_inexistente(env):
    client, ids, _ = env
    h = _token(client)
    r = _vincular_persona(client, h, ids["usuario_trabajador_id"], str(uuid.uuid4()))
    assert r.status_code == 404, r.text


def test_cuenta_desactivada_no_marca_con_mensaje_legible(env):
    """Una cuenta inactiva no debe caer en `verificar_pin_de` y salir como
    401 «credenciales inválidas» — sería el mismo error engañoso que
    `usuario_que_firma` existe para evitar."""
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids)
    r = client.patch(
        f"/api/v1/users/{ids['usuario_trabajador_id']}", headers=h, json={"activo": False}
    )
    assert r.status_code == 200, r.text

    hterm = _token(client, "pad-castilla", "999999")
    r = _marcar(client, hterm, ids, trabajador_id)
    assert r.status_code == 409, r.text
    assert "desactivada" in r.json()["detail"]


def test_locacion_de_servicios_no_marca_ni_aparece(env):
    """RN-PER-002: registrar asistencia a un RHE es desnaturalizar el
    vínculo. Ni sale en el pad ni se puede forzar."""
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(
        client, h, ids, tipo_vinculo="locacion_servicios", registra_asistencia=False
    )
    hterm = _token(client, "pad-castilla", "999999")

    assert _tarjetas(client, hterm, ids).json() == []
    assert _marcar(client, hterm, ids, trabajador_id).status_code == 409


def test_la_cuenta_del_pad_no_puede_hacer_nada_mas(env):
    """Una tablet robada no es un administrador: el rol trae un permiso."""
    client, ids, _ = env
    hterm = _token(client, "pad-castilla", "999999")
    assert client.get("/api/v1/rrhh/trabajadores", headers=hterm).status_code == 403
    assert _crear_turno(client, hterm, ids).status_code == 403


# --- Terminal enrolado y evidencia (ADR-079, RN-RRHH-023/024) -------------------
def test_marcar_sin_terminal_autorizado_da_403(env):
    """El PIN correcto no alcanza sin un terminal enrolado para el local:
    es exactamente el hueco que ADR-079 cierra — la sesión de la cuenta de
    servicio ya no basta para marcar desde cualquier navegador."""
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids)
    hterm = _token(client, "pad-castilla", "999999")
    assert _marcar(client, hterm, ids, trabajador_id, terminal=False).status_code == 403


def test_terminal_de_otra_sucursal_no_marca(env):
    client, ids, TestSession = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids)
    hterm = _token(client, "pad-castilla", "999999")

    with TestSession() as s:
        primera = s.get(Sucursal, uuid.UUID(ids["sucursal_id"]))
        otra = Sucursal(
            empresa_id=uuid.UUID(ids["empresa_id"]),
            marca_id=primera.marca_id,
            nombre="Otra",
            direccion="Av. Otra 1",
            tenencia="alquilada",
        )
        s.add(otra)
        s.flush()
        _, codigo = terminales_uc.crear(s, sucursal_id=otra.id, nombre="Pad")
        secreto_de_otra = terminales_uc.enrolar(s, sucursal_id=otra.id, codigo=codigo)
        s.commit()

    h2 = dict(hterm)
    h2["X-Terminal"] = secreto_de_otra
    r = client.post(
        f"/api/v1/rrhh/asistencia/terminal/marcar?sucursal_id={ids['sucursal_id']}",
        headers=h2,
        json={"trabajador_id": trabajador_id, "pin": PIN_TRABAJADOR},
    )
    assert r.status_code == 403


def test_enrolar_con_codigo_repetido_da_409(env):
    client, ids, TestSession = env
    hterm = _token(client, "pad-castilla", "999999")
    with TestSession() as s:
        _, codigo = terminales_uc.crear(
            s, sucursal_id=uuid.UUID(ids["sucursal_id"]), nombre="Barra"
        )
        s.commit()

    def _enrolar():
        return client.post(
            f"/api/v1/rrhh/asistencia/terminal/enrolar?sucursal_id={ids['sucursal_id']}",
            headers=hterm,
            json={"codigo": codigo},
        )

    assert _enrolar().status_code == 200
    # El código se borra al enrolar: usarlo de nuevo es el mismo error que
    # uno vencido — no hay forma de distinguirlos desde afuera.
    assert _enrolar().status_code == 409


def test_marcar_sin_evidencia_marca_igual_y_queda_en_null(env):
    """Sin permiso de cámara ni de ubicación, el marcaje no se bloquea
    (RN-RRHH-024): la evidencia es observación, nunca condición."""
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids)
    hterm = _token(client, "pad-castilla", "999999")

    r = _marcar(client, hterm, ids, trabajador_id)
    assert r.status_code == 200, r.text
    asistencia_id = r.json()["asistencia"]["id"]

    m = client.get(f"/api/v1/rrhh/asistencia/{asistencia_id}/marcaciones", headers=h)
    assert m.status_code == 200, m.text
    fila = m.json()[0]
    assert fila["tipo"] == "entrada"
    assert fila["distancia_m"] is None
    assert fila["tiene_foto"] is False
    assert fila["terminal_id"] is not None


def test_marcar_con_foto_queda_disponible_para_rrhh(env):
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids)
    hterm = _token(client, "pad-castilla", "999999")

    foto = base64.b64encode(b"contenido-jpeg-de-prueba").decode()
    r = _marcar(client, hterm, ids, trabajador_id, foto=foto, lat="-12.05", lng="-77.03")
    assert r.status_code == 200, r.text
    asistencia_id = r.json()["asistencia"]["id"]

    m = client.get(f"/api/v1/rrhh/asistencia/{asistencia_id}/marcaciones", headers=h)
    marcacion_id = m.json()[0]["id"]
    assert m.json()[0]["tiene_foto"] is True

    foto_r = client.get(f"/api/v1/rrhh/marcaciones/{marcacion_id}/foto", headers=h)
    assert foto_r.status_code == 200
    assert foto_r.content == b"contenido-jpeg-de-prueba"


def test_foto_que_supera_el_tope_se_rechaza(env):
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids)
    hterm = _token(client, "pad-castilla", "999999")

    # Justo por encima del tope de bytes decodificados, pero por debajo del
    # `max_length` del schema en base64: prueba el chequeo del router, no
    # solo la validación de pydantic.
    foto = base64.b64encode(b"x" * 130_001).decode()
    r = _marcar(client, hterm, ids, trabajador_id, foto=foto)
    assert r.status_code == 422


def test_correccion_de_backoffice_tambien_deja_evidencia(env):
    """`ASISTENCIA_MARCAR` (back-office) no pasa por el pad ni por un
    terminal: su `marcacion` queda con `terminal_id` en NULL."""
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids)

    r = client.post(
        "/api/v1/rrhh/asistencia/entrada",
        headers=h,
        json={
            "trabajador_id": trabajador_id,
            "fecha": "2026-08-24",
            "hora_entrada": "09:00:00",
        },
    )
    assert r.status_code == 201, r.text
    asistencia_id = r.json()["id"]

    m = client.get(f"/api/v1/rrhh/asistencia/{asistencia_id}/marcaciones", headers=h)
    assert m.status_code == 200, m.text
    assert m.json()[0]["terminal_id"] is None


def test_metros_entre_mismo_punto_es_cero():
    lat, lng = Decimal("-12.05"), Decimal("-77.03")
    assert metros_entre(lat, lng, lat, lng) == 0


def test_metros_entre_un_grado_de_latitud_son_unos_111_km():
    d = metros_entre(Decimal("0"), Decimal("0"), Decimal("1"), Decimal("0"))
    assert 110_000 < d < 112_000


# --- Barrido de salidas sin marcar -----------------------------------------------
def _entrada_vieja(TestSession, trabajador_id, turno_id, fecha):
    with TestSession() as s:
        s.add(
            Asistencia(
                trabajador_id=uuid.UUID(trabajador_id),
                fecha=fecha,
                hora_entrada=time(9, 0),
                turno_id=uuid.UUID(turno_id),
            )
        )
        s.commit()


def test_el_barrido_avisa_una_sola_vez(env):
    client, ids, TestSession = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids)
    turno_id = _crear_turno(client, h, ids).json()["id"]
    _entrada_vieja(TestSession, trabajador_id, turno_id, date(2026, 8, 24))

    momento = datetime(2026, 8, 24, 19, 0, tzinfo=LIMA)
    with TestSession() as s:
        avisadas = avisos_asistencia.barrer(s, momento)
        s.commit()
        assert len(avisadas) == 1
        # El recordatorio va a la campana del propio trabajador: no tiene
        # `rrhh.leer` y nunca podría abrir un reporte.
        notificacion = s.scalar(
            select(Notificacion).where(
                Notificacion.usuario_id == uuid.UUID(ids["usuario_trabajador_id"])
            )
        )
        assert notificacion is not None
        assert notificacion.tipo == "rrhh.salida_sin_marcar"

    with TestSession() as s:
        assert avisos_asistencia.barrer(s, momento) == []


def test_el_barrido_no_avisa_antes_de_la_hora_limite(env):
    client, ids, TestSession = env
    h = _token(client)
    trabajador_id = _crear_trabajador(client, h, ids)
    turno_id = _crear_turno(client, h, ids).json()["id"]
    _entrada_vieja(TestSession, trabajador_id, turno_id, date(2026, 8, 24))

    with TestSession() as s:
        antes = datetime(2026, 8, 24, 17, 30, tzinfo=LIMA)
        assert avisos_asistencia.barrer(s, antes) == []
