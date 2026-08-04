"""Restricciones JSONB por permiso (ADR-022): monto/estado/horario acotan
un permiso ya concedido — antes `permiso.restricciones` existía en el
esquema pero nada lo leía.
"""

from datetime import time
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.users.api.deps import check_permission
from src.modules.users.domain.rules import ContextoPermiso, cumple_restricciones
from src.modules.users.infrastructure.models import (
    Permiso,
    Rol,
    RolPermiso,
    Usuario,
    UsuarioRol,
)
from src.modules.users.infrastructure.repositories import UsuarioRepo
from src.modules.users.infrastructure.security import hash_pin


# --- cumple_restricciones (pura) ---------------------------------------------
def test_sin_restricciones_siempre_cumple():
    assert cumple_restricciones(None, ContextoPermiso()) is True
    assert cumple_restricciones({}, ContextoPermiso(monto=Decimal("999"))) is True


def test_monto_maximo():
    r = {"monto_maximo": "50.00"}
    assert cumple_restricciones(r, ContextoPermiso(monto=Decimal("50.00"))) is True
    assert cumple_restricciones(r, ContextoPermiso(monto=Decimal("50.01"))) is False
    # Sin monto en el contexto, esta dimensión no bloquea.
    assert cumple_restricciones(r, ContextoPermiso()) is True


def test_estados_permitidos():
    r = {"estados_permitidos": ["borrador", "emitida"]}
    assert cumple_restricciones(r, ContextoPermiso(estado="emitida")) is True
    assert cumple_restricciones(r, ContextoPermiso(estado="anulada")) is False
    assert cumple_restricciones(r, ContextoPermiso()) is True


def test_horario():
    r = {"horario": {"desde": "08:00", "hasta": "22:00"}}
    assert cumple_restricciones(r, ContextoPermiso(hora=time(12, 0))) is True
    assert cumple_restricciones(r, ContextoPermiso(hora=time(23, 0))) is False
    assert cumple_restricciones(r, ContextoPermiso()) is True


def test_varias_dimensiones_a_la_vez():
    r = {"monto_maximo": "50.00", "estados_permitidos": ["borrador"]}
    ok = ContextoPermiso(monto=Decimal("10"), estado="borrador")
    assert cumple_restricciones(r, ok) is True
    excede_monto = ContextoPermiso(monto=Decimal("100"), estado="borrador")
    assert cumple_restricciones(r, excede_monto) is False
    estado_no_permitido = ContextoPermiso(monto=Decimal("10"), estado="emitida")
    assert cumple_restricciones(r, estado_no_permitido) is False


# --- UsuarioRepo.restricciones (infra) ---------------------------------------
@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _usuario_con_permiso(session, codigo: str, restricciones: dict | None) -> Usuario:
    permiso = Permiso(codigo=codigo, restricciones=restricciones)
    rol = Rol(nombre=f"rol-{codigo}")
    usuario = Usuario(username=f"u-{codigo}", pin_hash=hash_pin("123456"), tipo="humano")
    session.add_all([permiso, rol, usuario])
    session.flush()
    session.add(RolPermiso(rol_id=rol.id, permiso_id=permiso.id))
    session.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))
    session.flush()
    return usuario


def test_repo_devuelve_las_restricciones_del_permiso(session):
    usuario = _usuario_con_permiso(session, "sales.aplicar_descuento", {"monto_maximo": "50"})
    assert UsuarioRepo(session).restricciones(usuario.id, "sales.aplicar_descuento") == {
        "monto_maximo": "50"
    }


def test_repo_sin_restricciones_devuelve_none(session):
    usuario = _usuario_con_permiso(session, "sales.aplicar_descuento", None)
    assert UsuarioRepo(session).restricciones(usuario.id, "sales.aplicar_descuento") is None


def test_repo_comodin_no_tiene_restriccion(session):
    permiso = Permiso(codigo="*", restricciones=None)
    rol = Rol(nombre="admin-test")
    usuario = Usuario(username="admin-test", pin_hash=hash_pin("123456"), tipo="humano")
    session.add_all([permiso, rol, usuario])
    session.flush()
    session.add(RolPermiso(rol_id=rol.id, permiso_id=permiso.id))
    session.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))
    session.flush()
    assert UsuarioRepo(session).restricciones(usuario.id, "sales.aplicar_descuento") is None


def test_repo_sin_el_permiso_devuelve_none(session):
    usuario = Usuario(username="sin-nada", pin_hash=hash_pin("123456"), tipo="humano")
    session.add(usuario)
    session.flush()
    assert UsuarioRepo(session).restricciones(usuario.id, "sales.aplicar_descuento") is None


# --- check_permission con contexto (deps.py) ---------------------------------
def test_check_permission_sin_contexto_ignora_restricciones(session):
    usuario = _usuario_con_permiso(session, "sales.aplicar_descuento", {"monto_maximo": "1"})
    check_permission(session, usuario, "sales.aplicar_descuento")  # no lanza


def test_check_permission_con_contexto_dentro_del_tope(session):
    usuario = _usuario_con_permiso(session, "sales.aplicar_descuento", {"monto_maximo": "50"})
    check_permission(
        session, usuario, "sales.aplicar_descuento",
        contexto=ContextoPermiso(monto=Decimal("50")),
    )  # no lanza


def test_check_permission_con_contexto_sobre_el_tope_403(session):
    usuario = _usuario_con_permiso(session, "sales.aplicar_descuento", {"monto_maximo": "50"})
    with pytest.raises(HTTPException) as exc:
        check_permission(
            session, usuario, "sales.aplicar_descuento",
            contexto=ContextoPermiso(monto=Decimal("50.01")),
        )
    assert exc.value.status_code == 403


def test_check_permission_sin_el_permiso_403_antes_de_mirar_restricciones(session):
    usuario = Usuario(username="sin-permiso", pin_hash=hash_pin("123456"), tipo="humano")
    session.add(usuario)
    session.flush()
    with pytest.raises(HTTPException) as exc:
        check_permission(
            session, usuario, "sales.aplicar_descuento",
            contexto=ContextoPermiso(monto=Decimal("1")),
        )
    assert exc.value.status_code == 403
