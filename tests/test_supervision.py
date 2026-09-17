"""Tests del módulo supervision: dominio (`toca_hoy`, checklist), generación
diaria idempotente, ejecución de tareas (permisos, checklist, foto/EXIF) y
cierre de jornada con emisión al catálogo de `reports`."""

import io
import uuid
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.supervision.application import generacion, informes, tareas
from src.modules.supervision.application.errors import Conflicto
from src.modules.supervision.application.tasks import purgar_fotos
from src.modules.supervision.domain import rules
from src.modules.supervision.infrastructure.models import TareaInstancia
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Empresa, Marca, Sucursal
from src.shared import fechas


# --- Dominio -------------------------------------------------------------------
def test_toca_hoy_diaria_siempre():
    assert rules.toca_hoy(
        frecuencia="diaria", fecha_inicio=date(2026, 1, 1), hoy=date(2026, 9, 17)
    )


def test_toca_hoy_nunca_antes_de_fecha_inicio():
    assert not rules.toca_hoy(
        frecuencia="diaria", fecha_inicio=date(2026, 9, 20), hoy=date(2026, 9, 17)
    )


def test_toca_hoy_interdiaria():
    inicio = date(2026, 9, 1)
    assert rules.toca_hoy(frecuencia="interdiaria", fecha_inicio=inicio, hoy=date(2026, 9, 1))
    assert not rules.toca_hoy(frecuencia="interdiaria", fecha_inicio=inicio, hoy=date(2026, 9, 2))
    assert rules.toca_hoy(frecuencia="interdiaria", fecha_inicio=inicio, hoy=date(2026, 9, 3))


def test_toca_hoy_semanal():
    inicio = date(2026, 9, 1)
    lunes = date(2026, 9, 14)  # lunes
    assert rules.toca_hoy(
        frecuencia="semanal", fecha_inicio=inicio, hoy=lunes, dia_semana=lunes.weekday()
    )
    assert not rules.toca_hoy(
        frecuencia="semanal", fecha_inicio=inicio, hoy=lunes + timedelta(days=1),
        dia_semana=lunes.weekday(),
    )


def test_toca_hoy_mensual():
    inicio = date(2026, 1, 1)
    assert rules.toca_hoy(
        frecuencia="mensual", fecha_inicio=inicio, hoy=date(2026, 9, 15), dia_mes=15
    )
    assert not rules.toca_hoy(
        frecuencia="mensual", fecha_inicio=inicio, hoy=date(2026, 9, 16), dia_mes=15
    )


def test_checklist_completo():
    assert rules.checklist_completo([{"texto": "a", "hecho": True}])
    assert not rules.checklist_completo([{"texto": "a", "hecho": False}])
    assert not rules.checklist_completo([])


def test_puede_ejecutar_sin_asignar_no_es_nadie():
    actor = uuid.uuid4()
    assert not rules.puede_ejecutar(None, actor)
    assert rules.puede_ejecutar(actor, actor)
    assert not rules.puede_ejecutar(uuid.uuid4(), actor)


def test_puede_completar_exige_foto_si_la_tarea_la_pide():
    checklist = [{"texto": "a", "hecho": True}]
    assert not rules.puede_completar(checklist=checklist, requiere_foto=True, tiene_foto=False)
    assert rules.puede_completar(checklist=checklist, requiere_foto=True, tiene_foto=True)
    assert rules.puede_completar(checklist=checklist, requiere_foto=False, tiene_foto=False)


def test_foto_es_de_ahora_none_sin_exif():
    assert rules.foto_es_de_ahora(None, datetime.now(), 15) is None


# --- Entorno de API --------------------------------------------------------------
@pytest.fixture()
def env(monkeypatch, _app_compartida, _engine_de_prueba):
    engine = _engine_de_prueba
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from src.modules.supervision.application import tasks as supervision_tasks

    monkeypatch.setattr(supervision_tasks, "session_factory", TestSession)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        marca = s.scalar(select(Marca))
        sucursales = list(s.scalars(select(Sucursal)))
        ids.update(
            empresa_id=str(empresa.id),
            marca_id=str(marca.id),
            sucursal_id=str(sucursales[0].id),
            sucursal_2_id=str(sucursales[1].id) if len(sucursales) > 1 else str(sucursales[0].id),
        )
        s.commit()

    app = _app_compartida

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


def _crear_categoria(client, h, ids, nombre="Limpieza"):
    r = client.post(
        "/api/v1/supervision/categorias",
        headers=h,
        json={"empresa_id": ids["empresa_id"], "nombre": nombre},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _crear_plantilla(client, h, ids, categoria_id, **overrides):
    body = {
        "empresa_id": ids["empresa_id"],
        "sucursal_id": ids["sucursal_id"],
        "categoria_id": categoria_id,
        "nombre": "Encender luces",
        "momento": "apertura",
        "orden": 1,
        "frecuencia": "diaria",
        "fecha_inicio": str(fechas.hoy()),
        "requiere_foto": False,
        "checklist": ["Verificar que enciendan todas"],
    }
    body.update(overrides)
    r = client.post("/api/v1/supervision/plantillas", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_crear_categoria_y_plantilla(env):
    client, ids, _ = env
    h = _token(client, "aprobador1", "123456")
    categoria = _crear_categoria(client, h, ids)
    plantilla = _crear_plantilla(client, h, ids, categoria["id"])
    assert plantilla["nombre"] == "Encender luces"
    assert plantilla["checklist"] == ["Verificar que enciendan todas"]


def test_plantilla_sin_marca_ni_sucursal_es_422(env):
    client, ids, _ = env
    h = _token(client, "aprobador1", "123456")
    categoria = _crear_categoria(client, h, ids)
    r = client.post(
        "/api/v1/supervision/plantillas",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "categoria_id": categoria["id"],
            "nombre": "x",
            "momento": "apertura",
            "frecuencia": "diaria",
            "fecha_inicio": str(fechas.hoy()),
            "checklist": ["a"],
        },
    )
    assert r.status_code == 422


def test_cajero_no_puede_crear_plantilla(env):
    client, ids, _ = env
    h_sup = _token(client, "aprobador1", "123456")
    categoria = _crear_categoria(client, h_sup, ids)
    h_cajero = _token(client, "cajero1", "123456")
    r = client.post(
        "/api/v1/supervision/plantillas",
        headers=h_cajero,
        json={
            "empresa_id": ids["empresa_id"],
            "sucursal_id": ids["sucursal_id"],
            "categoria_id": categoria["id"],
            "nombre": "x",
            "momento": "apertura",
            "frecuencia": "diaria",
            "fecha_inicio": str(fechas.hoy()),
            "checklist": ["a"],
        },
    )
    assert r.status_code == 403


def test_generacion_es_idempotente_y_cubre_toda_la_marca(env):
    """Una plantilla de marca (sin sucursal) genera una instancia por cada
    sucursal de esa marca, y correr la generación dos veces no duplica."""
    client, ids, TestSession = env
    h = _token(client, "aprobador1", "123456")
    categoria = _crear_categoria(client, h, ids)
    _crear_plantilla(
        client, h, ids, categoria["id"], sucursal_id=None, marca_id=ids["marca_id"]
    )

    r1 = client.post("/api/v1/supervision/tareas/generar", headers=h)
    assert r1.json()["generadas"] == 2  # dos sucursales sembradas
    r2 = client.post("/api/v1/supervision/tareas/generar", headers=h)
    assert r2.json()["generadas"] == 0

    with TestSession() as s:
        total = s.scalar(select(TareaInstancia)) is not None
        assert total
        filas = list(s.scalars(select(TareaInstancia)))
        assert len(filas) == 2
        assert {str(f.sucursal_id) for f in filas} == {ids["sucursal_id"], ids["sucursal_2_id"]}


def test_solo_el_asignado_ejecuta_su_tarea(env):
    client, ids, TestSession = env
    h_sup = _token(client, "aprobador1", "123456")
    categoria = _crear_categoria(client, h_sup, ids)
    _crear_plantilla(client, h_sup, ids, categoria["id"], checklist=["Paso 1"])
    client.post("/api/v1/supervision/tareas/generar", headers=h_sup)

    r = client.get(
        f"/api/v1/supervision/tareas?sucursal_id={ids['sucursal_id']}", headers=h_sup
    )
    instancia_id = r.json()[0]["id"]

    h_cajero = _token(client, "cajero1", "123456")
    # Sin asignar todavía: el cajero no puede marcar el checklist.
    r_sin_asignar = client.patch(
        f"/api/v1/supervision/tareas/{instancia_id}/checklist/0",
        headers=h_cajero,
        json={"hecho": True},
    )
    assert r_sin_asignar.status_code == 403

    with TestSession() as s:
        from src.modules.users.infrastructure.repositories import UsuarioRepo

        cajero = UsuarioRepo(s).get_by_username("cajero1")
        cajero_id = str(cajero.id)

    r_asignar = client.patch(
        f"/api/v1/supervision/tareas/{instancia_id}/asignar",
        headers=h_sup,
        json={"usuario_id": cajero_id},
    )
    assert r_asignar.status_code == 200

    # Otro trabajador (almacen1) sigue sin poder ejecutarla.
    h_otro = _token(client, "almacen1", "123456")
    r_otro = client.patch(
        f"/api/v1/supervision/tareas/{instancia_id}/checklist/0",
        headers=h_otro,
        json={"hecho": True},
    )
    assert r_otro.status_code == 403

    r_marcar = client.patch(
        f"/api/v1/supervision/tareas/{instancia_id}/checklist/0",
        headers=h_cajero,
        json={"hecho": True},
    )
    assert r_marcar.status_code == 200
    assert r_marcar.json()["checklist"][0]["hecho"] is True


def _foto_con_exif(fecha: datetime | None) -> bytes:
    img = Image.new("RGB", (20, 20), "blue")
    buf = io.BytesIO()
    if fecha is None:
        img.save(buf, format="JPEG")
    else:
        exif = img.getexif()
        exif[36867] = fecha.strftime("%Y:%m:%d %H:%M:%S")
        img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def test_completar_exige_checklist_completo_y_foto_si_la_pide(env):
    client, ids, TestSession = env
    h_sup = _token(client, "aprobador1", "123456")
    categoria = _crear_categoria(client, h_sup, ids)
    _crear_plantilla(
        client, h_sup, ids, categoria["id"], requiere_foto=True, checklist=["Paso 1"]
    )
    client.post("/api/v1/supervision/tareas/generar", headers=h_sup)
    r = client.get(f"/api/v1/supervision/tareas?sucursal_id={ids['sucursal_id']}", headers=h_sup)
    instancia_id = r.json()[0]["id"]

    with TestSession() as s:
        from src.modules.users.infrastructure.repositories import UsuarioRepo

        cajero = UsuarioRepo(s).get_by_username("cajero1")
        cajero_id = str(cajero.id)
    client.patch(
        f"/api/v1/supervision/tareas/{instancia_id}/asignar",
        headers=h_sup,
        json={"usuario_id": cajero_id},
    )

    h_cajero = _token(client, "cajero1", "123456")
    # Sin marcar el checklist ni subir foto: falla.
    r_sin_nada = client.post(
        f"/api/v1/supervision/tareas/{instancia_id}/completar", headers=h_cajero, json={}
    )
    assert r_sin_nada.status_code == 422

    client.patch(
        f"/api/v1/supervision/tareas/{instancia_id}/checklist/0",
        headers=h_cajero,
        json={"hecho": True},
    )
    # Checklist completo pero sin foto: sigue fallando (la tarea la exige).
    r_sin_foto = client.post(
        f"/api/v1/supervision/tareas/{instancia_id}/completar", headers=h_cajero, json={}
    )
    assert r_sin_foto.status_code == 422

    foto_de_ahora = _foto_con_exif(fechas.ahora())
    r_foto = client.post(
        f"/api/v1/supervision/tareas/{instancia_id}/foto",
        headers=h_cajero,
        files={"archivo": ("foto.jpg", foto_de_ahora, "image/jpeg")},
    )
    assert r_foto.status_code == 200, r_foto.text

    r_completar = client.post(
        f"/api/v1/supervision/tareas/{instancia_id}/completar", headers=h_cajero, json={}
    )
    assert r_completar.status_code == 200, r_completar.text
    salida = r_completar.json()
    assert salida["estado"] == "completada"
    assert salida["foto_valida"] is True
    assert salida["tiene_foto"] is True


def test_foto_de_ayer_se_marca_invalida_pero_no_bloquea(env):
    client, ids, TestSession = env
    h_sup = _token(client, "aprobador1", "123456")
    categoria = _crear_categoria(client, h_sup, ids)
    _crear_plantilla(
        client, h_sup, ids, categoria["id"], requiere_foto=True, checklist=["Paso 1"]
    )
    client.post("/api/v1/supervision/tareas/generar", headers=h_sup)
    r = client.get(f"/api/v1/supervision/tareas?sucursal_id={ids['sucursal_id']}", headers=h_sup)
    instancia_id = r.json()[0]["id"]

    with TestSession() as s:
        from src.modules.users.infrastructure.repositories import UsuarioRepo

        cajero = UsuarioRepo(s).get_by_username("cajero1")
        cajero_id = str(cajero.id)
    client.patch(
        f"/api/v1/supervision/tareas/{instancia_id}/asignar",
        headers=h_sup,
        json={"usuario_id": cajero_id},
    )
    h_cajero = _token(client, "cajero1", "123456")
    client.patch(
        f"/api/v1/supervision/tareas/{instancia_id}/checklist/0",
        headers=h_cajero,
        json={"hecho": True},
    )
    foto_de_ayer = _foto_con_exif(fechas.ahora() - timedelta(days=1))
    client.post(
        f"/api/v1/supervision/tareas/{instancia_id}/foto",
        headers=h_cajero,
        files={"archivo": ("foto.jpg", foto_de_ayer, "image/jpeg")},
    )
    r_completar = client.post(
        f"/api/v1/supervision/tareas/{instancia_id}/completar", headers=h_cajero, json={}
    )
    assert r_completar.status_code == 200
    assert r_completar.json()["foto_valida"] is False


def test_foto_sin_exif_deja_foto_valida_en_none(env):
    client, ids, TestSession = env
    h_sup = _token(client, "aprobador1", "123456")
    categoria = _crear_categoria(client, h_sup, ids)
    _crear_plantilla(
        client, h_sup, ids, categoria["id"], requiere_foto=True, checklist=["Paso 1"]
    )
    client.post("/api/v1/supervision/tareas/generar", headers=h_sup)
    r = client.get(f"/api/v1/supervision/tareas?sucursal_id={ids['sucursal_id']}", headers=h_sup)
    instancia_id = r.json()[0]["id"]

    with TestSession() as s:
        from src.modules.users.infrastructure.repositories import UsuarioRepo

        cajero = UsuarioRepo(s).get_by_username("cajero1")
        cajero_id = str(cajero.id)
    client.patch(
        f"/api/v1/supervision/tareas/{instancia_id}/asignar",
        headers=h_sup,
        json={"usuario_id": cajero_id},
    )
    h_cajero = _token(client, "cajero1", "123456")
    client.patch(
        f"/api/v1/supervision/tareas/{instancia_id}/checklist/0",
        headers=h_cajero,
        json={"hecho": True},
    )
    client.post(
        f"/api/v1/supervision/tareas/{instancia_id}/foto",
        headers=h_cajero,
        files={"archivo": ("foto.jpg", _foto_con_exif(None), "image/jpeg")},
    )
    r_completar = client.post(
        f"/api/v1/supervision/tareas/{instancia_id}/completar", headers=h_cajero, json={}
    )
    assert r_completar.status_code == 200
    assert r_completar.json()["foto_valida"] is None


# --- Casos de uso directos (informe, purga) --------------------------------------
def _sesion_con_seed(engine):
    from src.seeders.seed import seed

    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with TestSession() as s:
        seed(s)
        s.commit()
    return TestSession


def test_generar_informe_marca_vencidas_y_es_idempotente(_engine_de_prueba, monkeypatch):
    TestSession = _sesion_con_seed(_engine_de_prueba)
    with TestSession() as s:
        sucursal = s.scalar(select(Sucursal))
        hoy = fechas.hoy()
        generacion.generar_instancias(s, hoy)
        s.commit()

        informe = informes.generar_informe(
            s, sucursal_id=sucursal.id, fecha=hoy, ahora=fechas.ahora()
        )
        s.commit()
        assert informe.vencidas >= 0

        # Cualquier tarea que haya quedado pendiente pasa a vencida.
        pendientes = [
            t
            for t in s.scalars(
                select(TareaInstancia).where(
                    TareaInstancia.sucursal_id == sucursal.id, TareaInstancia.fecha == hoy
                )
            )
        ]
        assert all(t.estado != "pendiente" for t in pendientes)

        informe_id = informe.id
        segunda = informes.generar_informe(
            s, sucursal_id=sucursal.id, fecha=hoy, ahora=fechas.ahora()
        )
        assert segunda.id == informe_id


def test_generar_informe_emite_reporte_en_reports(_engine_de_prueba, monkeypatch):
    from src.modules.reports.application import listeners as reports_listeners
    from src.modules.reports.infrastructure.models import ReporteEmitido
    from src.modules.users.application import listeners as users_listeners

    TestSession = _sesion_con_seed(_engine_de_prueba)
    monkeypatch.setattr(reports_listeners, "session_factory", TestSession)
    monkeypatch.setattr(users_listeners, "session_factory", TestSession)

    with TestSession() as s:
        sucursal = s.scalar(select(Sucursal))
        hoy = fechas.hoy()
        informes.generar_informe(s, sucursal_id=sucursal.id, fecha=hoy, ahora=fechas.ahora())
        s.commit()

    with TestSession() as s:
        emitido = s.scalar(
            select(ReporteEmitido).where(
                ReporteEmitido.codigo_emision == "supervision.informe_diario_generado"
            )
        )
        assert emitido is not None


def test_purgar_fotos_vacia_binario_y_conserva_fila(_engine_de_prueba, monkeypatch):
    from src.modules.supervision.application import tasks as supervision_tasks

    TestSession = _sesion_con_seed(_engine_de_prueba)
    monkeypatch.setattr(supervision_tasks, "session_factory", TestSession)

    with TestSession() as s:
        sucursal = s.scalar(select(Sucursal))
        from src.modules.supervision.application.categorias import crear_categoria

        categoria = crear_categoria(s, empresa_id=sucursal.empresa_id, nombre="Limpieza")
        instancia = generacion.crear_tarea_manual(
            s,
            sucursal_id=sucursal.id,
            fecha=fechas.hoy(),
            momento="apertura",
            nombre="x",
            categoria_id=categoria.id,
            checklist=["a"],
        )
        instancia.foto = b"contenido"
        instancia.completada_at = fechas.ahora() - timedelta(days=40)
        instancia.estado = "completada"
        instancia_id = instancia.id
        s.commit()

    borradas = purgar_fotos()
    assert borradas == 1

    with TestSession() as s:
        fila = s.get(TareaInstancia, instancia_id)
        assert fila is not None
        assert fila.foto is None
        assert fila.estado == "completada"


def test_marcar_item_indice_invalido_404(_engine_de_prueba):
    TestSession = _sesion_con_seed(_engine_de_prueba)
    with TestSession() as s:
        from src.modules.users.infrastructure.repositories import UsuarioRepo

        sucursal = s.scalar(select(Sucursal))
        actor_id = UsuarioRepo(s).get_by_username("cajero1").id
        from src.modules.supervision.application.categorias import crear_categoria

        categoria = crear_categoria(s, empresa_id=sucursal.empresa_id, nombre="Limpieza")
        instancia = generacion.crear_tarea_manual(
            s,
            sucursal_id=sucursal.id,
            fecha=fechas.hoy(),
            momento="apertura",
            nombre="x",
            categoria_id=categoria.id,
            checklist=["a"],
            asignado_a=actor_id,
        )
        s.commit()
        from src.modules.supervision.application.errors import NoEncontrado

        with pytest.raises(NoEncontrado):
            tareas.marcar_item(s, instancia.id, 5, hecho=True, actor_id=instancia.asignado_a)


def test_completar_dos_veces_es_conflicto(_engine_de_prueba):
    TestSession = _sesion_con_seed(_engine_de_prueba)
    with TestSession() as s:
        from src.modules.users.infrastructure.repositories import UsuarioRepo

        sucursal = s.scalar(select(Sucursal))
        from src.modules.supervision.application.categorias import crear_categoria

        categoria = crear_categoria(s, empresa_id=sucursal.empresa_id, nombre="Limpieza")
        actor_id = UsuarioRepo(s).get_by_username("cajero1").id
        instancia = generacion.crear_tarea_manual(
            s,
            sucursal_id=sucursal.id,
            fecha=fechas.hoy(),
            momento="apertura",
            nombre="x",
            categoria_id=categoria.id,
            checklist=["a"],
            asignado_a=actor_id,
        )
        s.commit()
        tareas.marcar_item(s, instancia.id, 0, hecho=True, actor_id=actor_id)
        tareas.completar(
            s, instancia.id, actor_id=actor_id, ahora=fechas.ahora(), tolerancia_minutos=15
        )
        s.commit()
        with pytest.raises(Conflicto):
            tareas.completar(
                s, instancia.id, actor_id=actor_id, ahora=fechas.ahora(), tolerancia_minutos=15
            )
