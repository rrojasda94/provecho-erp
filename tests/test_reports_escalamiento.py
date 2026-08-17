"""La cadena de escalamiento de un reporte (RN-CTP-004, ADR-036).

Un reporte decía qué pasó y ahí moría. Lo que se prueba acá es lo que hace
falta para que sirva de herramienta: que se pueda elevar, que llegue a quien
responde en ese nivel, que quede el rastro de quién intentó qué, y que nada
de eso abra una puerta a los datos de otra empresa.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.app import create_app
from src.core.database import Base
from src.modules.reports.infrastructure.models import (
    Area,
    AreaMiembro,
    ReporteEmitido,
    ReporteEscalamiento,
)
from src.modules.users.api.deps import get_db, get_db_reportes
from src.modules.users.infrastructure.models import (
    Empresa,
    Grupo,
    Marca,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin
from src.shared.models import AuditLog


@pytest.fixture()
def api():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from src.seeders.seed import seed

    with Sesion() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        sucursal = s.scalar(select(Sucursal))
        # Una segunda empresa para probar que el escalamiento no cruza tenant.
        grupo = s.scalar(select(Grupo))
        marca = s.scalar(select(Marca))
        otra = Empresa(
            grupo_id=grupo.id, ruc="20600000009", razon_social="Otra EIRL",
            domicilio_fiscal="Lima", tipo="operativa",
            zona_tributaria="amazonia_ley27037",
        )
        s.add(otra)
        s.flush()
        suc_otra = Sucursal(
            marca_id=marca.id, empresa_id=otra.id, nombre="Ajena",
            direccion="Jr. Z 9", tenencia="alquilada",
        )
        s.add(suc_otra)
        s.flush()
        s.commit()
        ids = {
            "empresa": empresa,
            "sucursal": sucursal,
            "otra_empresa": otra,
            "suc_otra": suc_otra,
        }

        def _override():
            yield s

        app = create_app()
        app.dependency_overrides[get_db] = _override
        app.dependency_overrides[get_db_reportes] = _override
        with TestClient(app) as c:
            r = c.post(
                "/api/v1/auth/login", json={"username": "admin", "pin": "123456"}
            )
            c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
            yield c, s, ids


def _reporte(s, ids, *, empresa=None, sucursal=None, codigo="sales.venta_anulada",
             datos=None, referencia_tipo="venta"):
    reporte = ReporteEmitido(
        empresa_id=(empresa or ids["empresa"]).id if empresa is not False else None,
        sucursal_id=(sucursal or ids["sucursal"]).id if sucursal is not False else None,
        codigo_emision=codigo,
        titulo="Venta anulada",
        datos=datos or {},
        referencia_tipo=referencia_tipo,
        referencia_id=uuid.uuid4(),
    )
    s.add(reporte)
    s.commit()
    return reporte


def _abrir(c, reporte_id, *, motivo="queja", descripcion="El cliente reclamó"):
    return c.post(
        f"/api/v1/reports/emitidos/{reporte_id}/escalamientos",
        json={"motivo": motivo, "descripcion": descripcion},
    )


def _usuario(s, username, rol_nombre, sucursal):
    u = Usuario(username=username, pin_hash=hash_pin("654321"), tipo="humano")
    s.add(u)
    s.flush()
    rol = s.scalar(select(Rol).where(Rol.nombre == rol_nombre))
    s.add_all([
        UsuarioRol(usuario_id=u.id, rol_id=rol.id),
        UsuarioSucursal(usuario_id=u.id, sucursal_id=sucursal.id),
    ])
    s.commit()
    return u


def _token(c, username):
    r = c.post("/api/v1/auth/login", json={"username": username, "pin": "654321"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- Apertura -----------------------------------------------------------------
def test_abrir_un_escalamiento_arranca_en_supervisor(api):
    c, s, ids = api
    reporte = _reporte(s, ids)

    r = _abrir(c, reporte.id)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["nivel_actual"] == "supervisor"
    assert cuerpo["estado"] == "abierto"
    assert cuerpo["motivo"] == "queja"
    # El origen se deriva del reporte: pedírselo al que eleva es hacerle
    # repetir un dato que el ERP ya tiene, con chance de que lo repita mal.
    assert cuerpo["origen"] == "punto_venta"
    # La primera acción es la apertura: el historial arranca poblado.
    assert [a["accion"] for a in cuerpo["acciones"]] == ["abrir"]


def test_un_reporte_sin_empresa_no_se_escala(api):
    """RN-REP-011: un hecho que no se pudo atribuir no tiene área a la que
    elevarse ni permiso de módulo que lo cubra.

    409 y no 422 porque en este repo `ReglaNegocio` es conflicto de estado,
    no de forma del cuerpo (`core/error_handlers.py`).
    """
    c, s, ids = api
    reporte = _reporte(s, ids, empresa=False, sucursal=False)
    assert _abrir(c, reporte.id).status_code == 409


def test_no_hay_dos_cadenas_abiertas_sobre_el_mismo_reporte(api):
    """RN-REP-013. Dos cadenas dan dos verdades y dos responsables."""
    c, s, ids = api
    reporte = _reporte(s, ids)
    assert _abrir(c, reporte.id).status_code == 201
    assert _abrir(c, reporte.id).status_code == 409


def test_una_no_conformidad_desechada_exige_evidencia(api):
    """RN-PRD-015: si terminó en desecho, hay que poder ver la prueba."""
    c, s, ids = api
    reporte = _reporte(
        s,
        ids,
        codigo="production.no_conformidad_detectada",
        referencia_tipo="orden_produccion",
        datos={"resultado": "no_conforme_desechado"},
    )
    r = _abrir(c, reporte.id, motivo="no_conformidad_calidad", descripcion="Se desechó")
    assert r.status_code == 409

    conforme = _reporte(
        s,
        ids,
        codigo="production.no_conformidad_detectada",
        referencia_tipo="orden_produccion",
        datos={"resultado": "no_conforme_reproceso"},
    )
    ok = _abrir(
        c, conforme.id, motivo="no_conformidad_calidad", descripcion="Se reprocesa"
    )
    assert ok.status_code == 201
    # Origen `produccion`: lo dice el `referencia_tipo` del reporte.
    assert ok.json()["origen"] == "produccion"


# --- La cadena ----------------------------------------------------------------
def test_la_cadena_sube_de_a_un_escalon_y_no_se_reescribe(api):
    """RN-REP-012: el historial por nivel es el insumo de la mejora continua;
    un nivel que pisa lo del anterior lo convierte en la versión del último."""
    c, s, ids = api
    reporte = _reporte(s, ids)
    esc = _abrir(c, reporte.id).json()

    subida = c.post(
        f"/api/v1/reports/escalamientos/{esc['id']}/elevar",
        json={"descripcion": "No pude resolverlo en piso"},
    )
    assert subida.status_code == 200, subida.text
    assert subida.json()["nivel_actual"] == "comercial"
    assert subida.json()["estado"] == "escalado"

    gerencia = c.post(
        f"/api/v1/reports/escalamientos/{esc['id']}/elevar",
        json={"descripcion": "Necesita decisión de Gerencia"},
    ).json()
    assert gerencia["nivel_actual"] == "gerencia"
    assert [a["accion"] for a in gerencia["acciones"]] == ["abrir", "elevar", "elevar"]
    # Cada entrada dice desde qué nivel se elevó, no a cuál: el registro es de
    # quién intentó, que es lo que se mira después.
    assert [a["nivel"] for a in gerencia["acciones"]] == [
        "supervisor", "supervisor", "comercial",
    ]

    # Desde gerencia no hay a dónde subir.
    tope = c.post(
        f"/api/v1/reports/escalamientos/{esc['id']}/elevar",
        json={"descripcion": "y ahora?"},
    )
    assert tope.status_code == 409


def test_resolver_en_supervisor_cierra_la_cadena(api):
    """`resuelto_supervisor` no es cosmético: separa «se resolvió donde tenía
    que resolverse» de «hubo que subirlo»."""
    c, s, ids = api
    reporte = _reporte(s, ids)
    esc = _abrir(c, reporte.id).json()

    r = c.post(
        f"/api/v1/reports/escalamientos/{esc['id']}/resolver",
        json={"descripcion": "Se le cambió el plato"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "resuelto_supervisor"
    assert r.json()["cerrado_at"] is not None

    # Cerrado es cerrado: ni se eleva ni se le agregan acciones.
    assert c.post(
        f"/api/v1/reports/escalamientos/{esc['id']}/elevar",
        json={"descripcion": "tarde"},
    ).status_code == 409
    assert c.post(
        f"/api/v1/reports/escalamientos/{esc['id']}/acciones",
        json={"descripcion": "tarde"},
    ).status_code == 409


def test_un_escalamiento_cerrado_libera_el_reporte_para_otra_cadena(api):
    """Un problema que vuelve a pasar sobre el mismo hecho es exactamente lo
    que la mejora continua quiere ver dos veces, no una."""
    c, s, ids = api
    reporte = _reporte(s, ids)
    esc = _abrir(c, reporte.id).json()
    c.post(
        f"/api/v1/reports/escalamientos/{esc['id']}/resolver",
        json={"descripcion": "listo"},
    )
    assert _abrir(c, reporte.id, descripcion="volvió a pasar").status_code == 201

    historial = c.get(
        f"/api/v1/reports/emitidos/{reporte.id}/escalamientos"
    ).json()
    assert len(historial) == 2


def test_una_accion_no_cambia_de_nivel(api):
    c, s, ids = api
    reporte = _reporte(s, ids)
    esc = _abrir(c, reporte.id).json()
    r = c.post(
        f"/api/v1/reports/escalamientos/{esc['id']}/acciones",
        json={"descripcion": "Llamé al cliente, quedó en volver"},
    ).json()
    assert r["nivel_actual"] == "supervisor"
    assert r["estado"] == "abierto"
    assert [a["accion"] for a in r["acciones"]] == ["abrir", "accion"]


# --- A quién le llega ---------------------------------------------------------
def test_elevar_dice_a_quien_le_llega(api):
    """El reporte de la elevación se emite post-commit (ADR-016): sus
    entregas no existen todavía cuando hay que contestar. La respuesta
    resuelve el nivel de destino en vivo, que es lo que el que eleva
    necesita saber."""
    c, s, ids = api
    supervisor = _usuario(s, "sup_comercial", "supervisor", ids["sucursal"])
    area = s.scalar(
        select(Area).where(
            Area.empresa_id == ids["empresa"].id, Area.codigo == "comercial"
        )
    )
    s.add(AreaMiembro(area_id=area.id, usuario_id=supervisor.id))
    s.commit()

    reporte = _reporte(s, ids)
    esc = _abrir(c, reporte.id).json()
    subida = c.post(
        f"/api/v1/reports/escalamientos/{esc['id']}/elevar",
        json={"descripcion": "va a comercial"},
    ).json()
    assert "sup_comercial" in subida["destinatarios"]


def test_un_nivel_sin_nadie_devuelve_la_lista_vacia_y_no_miente(api):
    """RN-REP-005: la emisión se guarda igual y sale como fuga en la matriz.
    Que la respuesta lo diga es el punto — quien eleva no puede suponer que
    llegó."""
    c, s, ids = api
    area = s.scalar(
        select(Area).where(
            Area.empresa_id == ids["empresa"].id, Area.codigo == "comercial"
        )
    )
    for miembro in s.scalars(
        select(AreaMiembro).where(AreaMiembro.area_id == area.id)
    ):
        s.delete(miembro)
    s.commit()

    reporte = _reporte(s, ids)
    esc = _abrir(c, reporte.id).json()
    subida = c.post(
        f"/api/v1/reports/escalamientos/{esc['id']}/elevar",
        json={"descripcion": "a la nada"},
    ).json()
    assert subida["nivel_actual"] == "comercial"
    assert subida["destinatarios"] == []


# --- Seguridad ----------------------------------------------------------------
def test_un_reporte_de_otra_empresa_no_se_escala(api):
    """El tenant corta antes que todo lo demás (`exigir_reporte` →
    `FueraDeAlcance` → 403), igual que en cualquier otro recurso del ERP. El
    404 que no confirma existencia es el otro caso: mismo tenant, pero sin
    ser destinatario ni tener `reports.leer_todo`."""
    c, s, ids = api
    ajeno = _reporte(
        s, ids, empresa=ids["otra_empresa"], sucursal=ids["suc_otra"]
    )
    supervisor = _usuario(s, "sup_local", "supervisor", ids["sucursal"])
    assert supervisor is not None

    r = c.post(
        f"/api/v1/reports/emitidos/{ajeno.id}/escalamientos",
        json={"motivo": "queja", "descripcion": "x"},
        headers=_token(c, "sup_local"),
    )
    assert r.status_code == 403


def test_ser_destinatario_no_alcanza_para_escalar_lo_que_no_se_puede_ver(api):
    """RN-REP-002, la segunda puerta, también sobre el escalamiento: un
    cocinero puede recibir el aviso de un descuadre y no ver la caja."""
    c, s, ids = api
    from src.modules.reports.infrastructure.models import EntregaReporte

    cocinero = _usuario(s, "coci", "cocinero", ids["sucursal"])
    reporte = _reporte(
        s, ids, codigo="accounting.cierre_caja_irregular",
        referencia_tipo="cierre_caja",
    )
    s.add(
        EntregaReporte(
            reporte_emitido_id=reporte.id,
            usuario_id=cocinero.id,
            motivo="rol:cocinero",
        )
    )
    s.commit()

    r = c.post(
        f"/api/v1/reports/emitidos/{reporte.id}/escalamientos",
        json={"motivo": "queja", "descripcion": "x"},
        headers=_token(c, "coci"),
    )
    # Sin `reports.escalar` ni `accounting.leer`: no pasa ninguna de las dos.
    assert r.status_code == 403


def test_un_escalamiento_de_otra_empresa_no_se_lee(api):
    c, s, ids = api
    ajeno = _reporte(s, ids, empresa=ids["otra_empresa"], sucursal=ids["suc_otra"])
    fila = ReporteEscalamiento(
        empresa_id=ids["otra_empresa"].id,
        sucursal_id=ids["suc_otra"].id,
        reporte_emitido_id=ajeno.id,
        origen="punto_venta",
        motivo="queja",
        descripcion="ajeno",
        reportado_por_id=s.scalar(
            select(Usuario).where(Usuario.username == "admin")
        ).id,
    )
    s.add(fila)
    s.commit()
    _usuario(s, "sup_local2", "supervisor", ids["sucursal"])

    r = c.get(
        f"/api/v1/reports/escalamientos/{fila.id}", headers=_token(c, "sup_local2")
    )
    assert r.status_code == 403


# --- Rastro -------------------------------------------------------------------
def test_cada_movimiento_del_escalamiento_queda_auditado(api):
    """RN-REP-014: elevar y resolver son actos de autoridad, igual que crear
    un área o cambiar una regla."""
    c, s, ids = api
    reporte = _reporte(s, ids)
    esc = _abrir(c, reporte.id).json()
    c.post(
        f"/api/v1/reports/escalamientos/{esc['id']}/acciones",
        json={"descripcion": "llamé"},
    )
    c.post(
        f"/api/v1/reports/escalamientos/{esc['id']}/elevar",
        json={"descripcion": "no pude"},
    )
    c.post(
        f"/api/v1/reports/escalamientos/{esc['id']}/resolver",
        json={"descripcion": "resuelto en comercial"},
    )

    acciones = [
        fila.accion
        for fila in s.scalars(
            select(AuditLog).where(AuditLog.entidad == "reporte_escalamiento")
        )
    ]
    assert sorted(acciones) == ["abrir", "accion", "elevar", "resolver"]


def test_la_bandeja_filtra_por_nivel_y_estado(api):
    c, s, ids = api
    abierto = _abrir(c, _reporte(s, ids).id).json()
    elevado = _abrir(c, _reporte(s, ids).id).json()
    c.post(
        f"/api/v1/reports/escalamientos/{elevado['id']}/elevar",
        json={"descripcion": "sube"},
    )

    en_comercial = c.get(
        "/api/v1/reports/escalamientos", params={"nivel_actual": "comercial"}
    ).json()
    assert [e["id"] for e in en_comercial["items"]] == [elevado["id"]]

    abiertos = c.get(
        "/api/v1/reports/escalamientos", params={"estado": "abierto"}
    ).json()
    assert [e["id"] for e in abiertos["items"]] == [abierto["id"]]
