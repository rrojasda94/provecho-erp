"""Auditoría transversal (ADR-029): escritura desde `shared`, lectura por
`/api/v1/auditoria` con alcance de tenant.

Lo que se congela acá es lo que hace útil al rastro: que cualquier módulo
pueda escribirlo sin importar `users`, que el detalle con PII no salga al
log, y que leerlo respete el alcance del que pregunta — un contador de una
empresa no puede ver lo que pasó en otra.
"""

import logging
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
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin
from src.shared import auditoria
from src.shared.models import AuditLog


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
        # Segunda empresa: sin ella no se puede probar que el alcance filtre.
        otra = Empresa(
            grupo_id=empresa.grupo_id, ruc="20999999999",
            razon_social="Otra Empresa SAC", domicilio_fiscal="Jr. Y 456",
            tipo="operativa",
        )
        s.add(otra)
        contador = Usuario(
            username="contador1", pin_hash=hash_pin("333333"), tipo="humano"
        )
        cajero = Usuario(username="cajero1", pin_hash=hash_pin("111111"), tipo="humano")
        s.add_all([contador, cajero])
        s.flush()
        for usuario, rol_nombre in ((contador, "contador"), (cajero, "cajero")):
            rol = s.scalar(select(Rol).where(Rol.nombre == rol_nombre))
            s.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))
            s.add(UsuarioSucursal(usuario_id=usuario.id, sucursal_id=sucursal.id))
        ids.update(
            empresa_id=empresa.id, otra_empresa_id=otra.id, sucursal_id=sucursal.id,
            contador_id=contador.id, cajero_id=cajero.id,
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
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _sembrar_rastro(TestSession, ids) -> None:
    with TestSession() as s:
        auditoria.registrar(
            s, entidad="venta", entidad_id=uuid.uuid4(), accion="anular",
            empresa_id=None, sucursal_id=ids["sucursal_id"],
        )
        auditoria.registrar(
            s, entidad="movimiento_dinero", entidad_id=uuid.uuid4(),
            accion="ejecutar_pago", empresa_id=ids["empresa_id"],
        )
        auditoria.registrar(
            s, entidad="orden_compra", entidad_id=uuid.uuid4(), accion="emitir",
            empresa_id=ids["otra_empresa_id"],
        )
        # Sin tenant: un acto global (alta de rol, login).
        auditoria.registrar(s, entidad="usuario_rol", accion="asignar_rol")
        s.commit()


def test_registrar_deja_fila_y_log_solo_con_metadatos(env, caplog):
    _, ids, TestSession = env
    entidad_id = uuid.uuid4()
    with caplog.at_level(logging.INFO, logger="provecho.auditoria"):
        with TestSession() as s:
            auditoria.registrar(
                s,
                entidad="persona",
                entidad_id=entidad_id,
                accion="anonimizar",
                datos_despues={"motivo": "pedido del titular", "dni": "44556677"},
                empresa_id=ids["empresa_id"],
            )
            s.commit()

    with TestSession() as s:
        fila = s.scalar(select(AuditLog).where(AuditLog.entidad_id == entidad_id))
    assert fila.accion == "anonimizar"
    assert fila.datos_despues["motivo"] == "pedido del titular"
    assert fila.empresa_id == ids["empresa_id"]
    assert fila.ts is not None

    registro = next(r for r in caplog.records if r.name == "provecho.auditoria")
    assert registro.accion == "anonimizar"
    assert registro.entidad == "persona"
    # El detalle puede traer PII (Ley 29733): se queda en la tabla.
    assert not hasattr(registro, "datos_despues")


def test_alcance_de_tenant_al_listar(env):
    _, ids, TestSession = env
    _sembrar_rastro(TestSession, ids)

    with TestSession() as s:
        # Superusuario sin empresa: sin filtro, ve incluso lo que no tiene tenant.
        todo = s.scalars(auditoria.q_listar()).all()
        assert len(todo) == 4

        propio = s.scalars(
            auditoria.q_listar(
                empresa_id=ids["empresa_id"],
                sucursal_ids=frozenset({ids["sucursal_id"]}),
            )
        ).all()
        assert {f.entidad for f in propio} == {"venta", "movimiento_dinero"}

        # Usuario sin empresa y sin sucursales: el caso ambiguo cierra, no abre.
        assert (
            s.scalars(auditoria.q_listar(sucursal_ids=frozenset())).all() == []
        )


def test_listar_exige_permiso(env):
    client, _, _ = env
    r = client.get("/api/v1/auditoria", headers=_token(client, "cajero1", "111111"))
    assert r.status_code == 403


def test_superusuario_ve_todo_y_filtra_por_entidad(env):
    client, ids, TestSession = env
    _sembrar_rastro(TestSession, ids)
    h = _token(client)

    r = client.get("/api/v1/auditoria", headers=h)
    assert r.status_code == 200
    entidades = {i["entidad"] for i in r.json()["items"]}
    # Incluidas las filas sin tenant y su propio login: el rastro de RBAC y
    # de sesiones no tiene empresa, y alguien tiene que poder leerlo.
    assert {"venta", "movimiento_dinero", "orden_compra", "usuario_rol"} <= entidades
    assert "usuario" in entidades

    r2 = client.get("/api/v1/auditoria?entidad=venta", headers=h)
    assert r2.json()["total"] == 1
    assert r2.json()["items"][0]["accion"] == "anular"


def test_contador_no_ve_el_rastro_de_otra_empresa(env):
    client, ids, TestSession = env
    _sembrar_rastro(TestSession, ids)

    r = client.get(
        "/api/v1/auditoria", headers=_token(client, "contador1", "333333")
    )
    assert r.status_code == 200
    entidades = {i["entidad"] for i in r.json()["items"]}
    assert entidades == {"venta", "movimiento_dinero"}
    assert "orden_compra" not in entidades


def test_no_hay_endpoint_de_escritura(env):
    """El rastro lo escribe el caso de uso, no el cliente: si algún día
    aparece un POST, el auditado podría dictar lo que dice su auditoría."""
    client, _, _ = env
    r = client.post("/api/v1/auditoria", headers=_token(client), json={})
    assert r.status_code == 405


def test_retiro_de_efectivo_queda_en_el_rastro(env):
    """Wiring de un módulo que antes no auditaba nada (accounting)."""
    from src.modules.accounting.application import caja
    from tests.conftest import abrir_caja_directa

    client, ids, TestSession = env
    with TestSession() as s:
        from src.modules.sales.infrastructure.models import PuntoVenta

        pv = PuntoVenta(
            sucursal_id=ids["sucursal_id"], canal="trabajador",
            serie_boleta="B001", serie_factura="F001", politica_pago="adelantado",
        )
        s.add(pv)
        s.flush()
        apertura = abrir_caja_directa(
            s, punto_venta_id=pv.id, cajero_id=ids["cajero_id"], monto="100.00"
        )
        caja.registrar_movimiento_caja(
            s,
            apertura.id,
            tipo="retiro",
            monto=Decimal("40.00"),
            motivo="pago al repartidor",
            registrado_por=ids["cajero_id"],
            idempotency_key="retiro-1",
            autorizado_por=ids["contador_id"],
        )
        s.commit()

    with TestSession() as s:
        fila = s.scalar(
            select(AuditLog).where(AuditLog.entidad == "movimiento_caja")
        )
    assert fila.accion == "retiro_efectivo"
    assert fila.datos_despues["monto"] == "40.00"
    assert fila.datos_despues["autorizado_por"] == str(ids["contador_id"])
