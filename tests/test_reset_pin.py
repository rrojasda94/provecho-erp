"""Reseteo de PIN y cambio obligatorio.

Un PIN olvidado no se recupera —está hasheado con Argon2id—, así que la única
salida es ponerle uno conocido. Eso deja por un rato una cuenta cuyo PIN sabe
alguien más, y lo que hace que eso sea aceptable es lo que se prueba acá: que
la marca **bloquea de verdad** el resto del ERP hasta cambiarlo.

Lo primero que hay que probar es justamente eso: si el filtro de rutas
permitidas queda mal, un reseteo deja a alguien sin poder ni cambiar su PIN.
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
from src.modules.users.infrastructure.models import Rol, Usuario, UsuarioRol
from src.modules.users.infrastructure.security import hash_pin


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
        for username, rol in (("olvidadizo", "cajero"), ("rrhh", "rrhh_admin")):
            u = Usuario(username=username, pin_hash=hash_pin("987654"), tipo="humano")
            s.add(u)
            s.flush()
            s.add(
                UsuarioRol(
                    usuario_id=u.id,
                    rol_id=s.scalar(select(Rol).where(Rol.nombre == rol)).id,
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


def _token(client, username, pin):
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _id_de(TestSession, username):
    with TestSession() as s:
        return str(s.scalar(select(Usuario).where(Usuario.username == username)).id)


def test_el_pin_reseteado_bloquea_todo_menos_cambiarlo(env):
    """Lo primero que hay que probar: la obligación se hace cumplir en el
    servidor. Sin esto, "cambio obligatorio" es un cartel que se cierra con
    la X."""
    client, TestSession = env
    usuario_id = _id_de(TestSession, "olvidadizo")
    admin = _token(client, "admin", "123456")

    assert client.post(
        f"/api/v1/users/{usuario_id}/pin/reset", headers=admin
    ).status_code == 204

    # Entra con el PIN por defecto, que es el punto del reseteo.
    h = _token(client, "olvidadizo", "123456")

    # Y no puede hacer nada más que verse, cambiarlo y salir. `sales/carta` es
    # una pantalla que este rol **sí** tiene permitida: si se probara con una
    # que le está negada igual, el 403 no diría nada.
    assert client.get("/api/v1/users/me", headers=h).status_code == 200
    assert client.get("/api/v1/sales/productos", headers=h).status_code == 403

    cambio = client.post(
        "/api/v1/users/me/pin",
        headers=h,
        json={"pin_actual": "123456", "pin_nuevo": "555111"},
    )
    assert cambio.status_code == 204, cambio.text

    # Con el PIN nuevo la cuenta vuelve a funcionar, y con el **mismo token**:
    # la marca se lee de la base en cada request, no del claim con el que se
    # emitió, así que un reseteo surte efecto sin esperar a que venza nada.
    assert client.get("/api/v1/sales/productos", headers=h).status_code == 200
    assert _token(client, "olvidadizo", "555111")


def test_el_reseteo_revoca_las_sesiones_abiertas(env):
    """Si se resetea por sospecha, dejar viva la sesión que ya estaba abierta
    no cierra nada."""
    client, TestSession = env
    usuario_id = _id_de(TestSession, "olvidadizo")
    login = client.post(
        "/api/v1/auth/login", json={"username": "olvidadizo", "pin": "987654"}
    ).json()

    client.post(
        f"/api/v1/users/{usuario_id}/pin/reset",
        headers=_token(client, "admin", "123456"),
    )

    r = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert r.status_code == 401, r.text


def test_el_reseteo_desbloquea_el_lockout(env):
    """Quien olvidó su PIN normalmente lo agotó intentando. Dejarlo bloqueado
    convierte el reseteo en nada."""
    client, TestSession = env
    usuario_id = _id_de(TestSession, "olvidadizo")
    for _ in range(6):
        client.post(
            "/api/v1/auth/login", json={"username": "olvidadizo", "pin": "000000"}
        )
    bloqueado = client.post(
        "/api/v1/auth/login", json={"username": "olvidadizo", "pin": "987654"}
    )
    # 423 Locked: la cuenta existe y el PIN es correcto, lo que falla es el
    # lockout. Distinto del 401 de credenciales, que no dice si el usuario
    # existe.
    assert bloqueado.status_code == 423

    client.post(
        f"/api/v1/users/{usuario_id}/pin/reset",
        headers=_token(client, "admin", "123456"),
    )
    assert _token(client, "olvidadizo", "123456")


def test_rrhh_resetea_pero_no_administra_usuarios(env):
    """El permiso es propio en los dos sentidos: RRHH atiende el "me olvidé
    el PIN" sin poder crear cuentas ni repartir roles."""
    client, TestSession = env
    usuario_id = _id_de(TestSession, "olvidadizo")
    rrhh = _token(client, "rrhh", "987654")

    assert client.post(
        f"/api/v1/users/{usuario_id}/pin/reset", headers=rrhh
    ).status_code == 204
    # Fijar un PIN a dedo sigue siendo `users.gestionar`.
    assert client.post(
        f"/api/v1/users/{usuario_id}/pin", headers=rrhh, json={"pin": "111222"}
    ).status_code == 403
    assert client.post(
        "/api/v1/users",
        headers=rrhh,
        json={"username": "nuevo", "pin": "112233"},
    ).status_code == 403


def test_el_cajero_no_resetea_el_pin_de_nadie(env):
    """Poder entrar como cualquiera de su turno rompe la segregación con la
    que está armado el ciclo de caja (ADR-025)."""
    client, TestSession = env
    rrhh_id = _id_de(TestSession, "rrhh")
    cajero = _token(client, "olvidadizo", "987654")
    assert client.post(
        f"/api/v1/users/{rrhh_id}/pin/reset", headers=cajero
    ).status_code == 403


def test_el_pin_propio_exige_el_actual_y_rechaza_el_de_fabrica(env):
    client, _ = env
    h = _token(client, "olvidadizo", "987654")

    equivocado = client.post(
        "/api/v1/users/me/pin",
        headers=h,
        json={"pin_actual": "000000", "pin_nuevo": "555111"},
    )
    assert equivocado.status_code == 422, equivocado.text

    # Cambiarlo por el que pone el reseteo es no cambiarlo.
    defecto = client.post(
        "/api/v1/users/me/pin",
        headers=h,
        json={"pin_actual": "987654", "pin_nuevo": "123456"},
    )
    assert defecto.status_code == 422, defecto.text


def test_no_se_resetea_el_pin_de_un_agente(env):
    """Una cuenta de agente no tiene PIN: se le rota el token (ADR-032).
    Resetearla dejaría una integración caída sin decir por qué."""
    client, TestSession = env
    with TestSession() as s:
        agente = Usuario(
            username="bot", pin_hash=hash_pin("999999"), tipo="agente_ia"
        )
        s.add(agente)
        s.commit()
        agente_id = str(agente.id)

    r = client.post(
        f"/api/v1/users/{agente_id}/pin/reset",
        headers=_token(client, "admin", "123456"),
    )
    assert r.status_code == 409, r.text


def test_el_reseteo_queda_auditado(env):
    """Un administrador puede dejar entrar a cualquiera como cualquiera. La
    contracara es que quede escrito quién lo hizo."""
    from src.shared.auditoria import AuditLog

    client, TestSession = env
    usuario_id = _id_de(TestSession, "olvidadizo")
    client.post(
        f"/api/v1/users/{usuario_id}/pin/reset",
        headers=_token(client, "admin", "123456"),
    )
    with TestSession() as s:
        fila = s.scalar(
            select(AuditLog).where(AuditLog.accion == "resetear_pin")
        )
    assert fila is not None
    assert str(fila.entidad_id) == usuario_id
    assert fila.usuario_id is not None
