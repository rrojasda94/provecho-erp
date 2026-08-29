"""Equivalencia entre `bi_alcance_usuario` (vista, ADR-083) y `Tenant`
(`src/core/tenant.py`, ADR-004).

Es la única defensa contra que los dos puntos de aplicación del tenant
diverjan en silencio: si esta vista se queda atrás de un cambio en cómo se
resuelve el alcance de un usuario, alguien ve en Superset una sucursal que en
Provecho no vería. Sin este test, esa fuga no se nota hasta que un usuario la
reporta.

Corre contra Postgres real, no contra el `create_all` de SQLite del resto del
suite: la vista es SQL puro creado por una migración, y `CREATE VIEW` no
existe en el motor que usan los demás tests. Se salta solo si no hay un
Postgres migrado y accesible en `settings.database_url` — en el job
`migraciones` de CI sí lo hay (ver `.github/workflows/ci.yml`); en una
máquina de desarrollo sin ese Postgres levantado, este archivo simplemente no
corre, en vez de fallar por una conexión que nadie pidió."""

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.modules.users.domain import rules
from src.modules.users.infrastructure.models import Permiso, Rol, RolPermiso, Usuario, UsuarioRol
from src.modules.users.infrastructure.repositories import UsuarioRepo
from src.modules.users.infrastructure.security import hash_pin


def _engine_postgres_o_none():
    if not settings.database_url.startswith("postgresql"):
        return None
    # `connect_timeout` corto a propósito (mismo criterio que
    # `CONNECT_TIMEOUT_SEGUNDOS` de `src/core/database.py`): sin él, en una
    # máquina sin Postgres levantado esta sonda no falla rápido con "conexión
    # rechazada" — se queda esperando en el `connect()` del socket varios
    # minutos, y "se salta si no hay Postgres" deja de ser cierto.
    engine = create_engine(
        settings.database_url, connect_args={"connect_timeout": 1}
    )
    try:
        with engine.connect() as con:
            con.execute(text("SELECT 1 FROM bi_alcance_usuario LIMIT 0"))
    except (OperationalError, ProgrammingError):
        return None
    return engine


_engine = _engine_postgres_o_none()

pytestmark = pytest.mark.skipif(
    _engine is None,
    reason="requiere Postgres migrado con vw_bi_* (job `migraciones` de CI)",
)


def _alcance_segun_vista(session: Session, username: str) -> set[uuid.UUID]:
    filas = session.execute(
        text("SELECT sucursal_id FROM bi_alcance_usuario WHERE username = :u"),
        {"u": username},
    ).all()
    return {fila[0] for fila in filas}


def _alcance_segun_tenant(session: Session, usuario_id: uuid.UUID) -> set[uuid.UUID]:
    """Mismo cálculo que `build_claims` (`src/modules/users/application/auth.py`):
    las sucursales de `usuario_sucursal`, filtrando las borradas."""
    return set(UsuarioRepo(session).sucursal_ids(usuario_id))


def _es_superusuario(session: Session, usuario_id: uuid.UUID) -> bool:
    return rules.permite(UsuarioRepo(session).permiso_codigos(usuario_id), "*")


@pytest.fixture()
def session():
    with Session(_engine) as s:
        yield s


@pytest.mark.parametrize("username", ["admin", "cajero1"])
def test_alcance_de_usuarios_semilla_coincide_con_tenant(session, username):
    """Los usuarios que crea `src/seeders/seed.py` (PIN 123456) tienen
    `usuario_sucursal` explícito para cada sucursal — este es el camino
    común, el que toma cualquier usuario del día a día."""
    usuario = session.query(Usuario).filter_by(username=username).one_or_none()
    if usuario is None:
        pytest.skip(f"usuario semilla '{username}' no existe — ¿falta el seeder?")

    esperado = _alcance_segun_tenant(session, usuario.id)
    if not esperado and _es_superusuario(session, usuario.id):
        pytest.skip(
            f"'{username}' es superusuario sin usuario_sucursal — cubierto por "
            "test_superusuario_sin_sucursales_ve_todas_las_de_la_vista"
        )

    obtenido = _alcance_segun_vista(session, username)
    assert obtenido == esperado, (
        f"bi_alcance_usuario diverge de Tenant.sucursal_ids para '{username}': "
        f"vista={obtenido} tenant={esperado}"
    )


def test_superusuario_sin_sucursales_ve_todas_las_de_la_vista(session):
    """El caso que `Tenant` resuelve con un bypass (`if self.superusuario:
    return` en `exigir_sucursal`) y que la vista no puede replicar como
    bypass —Superset necesita una lista concreta de filas—, así que lo
    traduce a "todas las sucursales no borradas". Es la cuenta de
    administración/setup de ADR-004: existe antes que cualquier
    `usuario_sucursal`."""
    username = f"_test_bi_super_{uuid.uuid4().hex[:8]}"
    usuario = Usuario(
        username=username,
        pin_hash=hash_pin("123456"),
        tipo="humano",
        activo=True,
    )
    session.add(usuario)
    session.flush()

    rol = Rol(nombre=f"_test_bi_rol_{uuid.uuid4().hex[:8]}")
    session.add(rol)
    session.flush()

    permiso_todo = session.query(Permiso).filter_by(codigo="*").one_or_none()
    if permiso_todo is None:
        pytest.skip("el seeder no cargó el permiso '*' — nada que comparar")

    session.add(RolPermiso(rol_id=rol.id, permiso_id=permiso_todo.id))
    session.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))
    session.commit()

    try:
        assert _es_superusuario(session, usuario.id)
        assert _alcance_segun_tenant(session, usuario.id) == set()

        todas_las_sucursales = {
            fila[0]
            for fila in session.execute(
                text("SELECT id FROM sucursal WHERE deleted_at IS NULL")
            ).all()
        }
        obtenido = _alcance_segun_vista(session, username)
        assert obtenido == todas_las_sucursales
    finally:
        # No es un usuario semilla: el test lo crea y lo limpia, para no
        # ensuciar la base que comparten los demás casos de este archivo.
        session.execute(
            text("DELETE FROM usuario_rol WHERE usuario_id = :u"), {"u": usuario.id}
        )
        session.execute(
            text("DELETE FROM rol_permiso WHERE rol_id = :r"), {"r": rol.id}
        )
        session.execute(text("DELETE FROM rol WHERE id = :r"), {"r": rol.id})
        session.execute(text("DELETE FROM usuario WHERE id = :u"), {"u": usuario.id})
        session.commit()
