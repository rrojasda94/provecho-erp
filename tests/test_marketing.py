"""Tests del slice core de marketing: campaña (brief → aprobada → en_curso),
contenido (RN-MKT-001/002), lead con atribución a la venta y encuesta de
satisfacción sobre venta entregada (RN-COM-007).

SQLite en memoria + override de get_db, mismo patrón que test_production.py.
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
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    Receta,
    UnidadMedida,
)
from src.modules.marketing.application import listeners
from src.modules.marketing.infrastructure.models import Lead
from src.modules.sales.infrastructure.models import (
    Cliente,
    ProductoComercial,
    PuntoVenta,
    Venta,
    VentaItem,
)
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Empresa,
    Marca,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin
from src.shared import fechas


@pytest.fixture()
def env(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(listeners, "session_factory", TestSession)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        marca = s.scalar(select(Marca))
        sucursal = s.scalar(select(Sucursal))

        udm_cat = CategoriaUdm(nombre="Unidad")
        s.add(udm_cat)
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Unidad", ratio=Decimal(1))
        s.add(udm)
        s.flush()
        articulo = Articulo(
            empresa_id=empresa.id,
            id_interno="P001",
            nombre="Pizza",
            unidad_medida_id=udm.id,
            tipo="producto_terminado",
        )
        s.add(articulo)
        s.flush()
        receta = Receta(
            empresa_id=empresa.id,
            nombre="Pizza (BOM)",
            rendimiento_cantidad=Decimal(1),
            rendimiento_unidad_medida_id=udm.id,
            articulo_id=articulo.id,
        )
        s.add(receta)
        s.flush()
        producto = ProductoComercial(
            id_interno="C001", marca_id=marca.id, nombre="Pizza", receta_id=receta.id
        )
        punto_venta = PuntoVenta(
            sucursal_id=sucursal.id,
            canal="trabajador",
            serie_boleta="B001",
            serie_factura="F001",
            politica_pago="al_finalizar",
        )
        cliente = Cliente(grupo_id=marca.grupo_id, tipo="natural", contacto="999888777")
        s.add_all([producto, punto_venta, cliente])
        s.flush()

        mkt = Usuario(username="mkt1", pin_hash=hash_pin("111111"), tipo="humano")
        s.add(mkt)
        s.flush()
        rol_mkt = s.scalar(select(Rol).where(Rol.nombre == "marketing"))
        s.add(UsuarioRol(usuario_id=mkt.id, rol_id=rol_mkt.id))
        s.add(UsuarioSucursal(usuario_id=mkt.id, sucursal_id=sucursal.id))

        ids.update(
            empresa_id=str(empresa.id),
            marca_id=str(marca.id),
            sucursal_id=str(sucursal.id),
            punto_venta_id=str(punto_venta.id),
            producto_id=str(producto.id),
            cliente_id=str(cliente.id),
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


def _crear_campana(client, headers, ids, *, key="mkt-key-1", con_brief=True, nombre="Verano"):
    body = {
        "marca_id": ids["marca_id"],
        "nombre": nombre,
        "tipo": "impulso_venta",
        "canal": "instagram",
        "idempotency_key": key,
    }
    if con_brief:
        body |= {
            "objetivo": "Subir el ticket promedio 10%",
            "publico_objetivo": "Clientes de 18-35 en Castilla",
            "presupuesto": "3000.00",
            "kpi": "ticket_promedio",
        }
    return client.post("/api/v1/marketing/campanas", headers=headers, json=body)


def _lanzar(client, headers, campana_id):
    client.post(f"/api/v1/marketing/campanas/{campana_id}/aprobacion", headers=headers)
    return client.post(
        f"/api/v1/marketing/campanas/{campana_id}/lanzamiento", headers=headers
    )


def _venta(TestSession, ids, *, entregada: bool, con_cliente: bool = True, numero=1):
    """Venta mínima con un ítem, escrita directo — marketing solo lee su
    estado de entrega por el contrato público de sales."""
    with TestSession() as s:
        venta = Venta(
            sucursal_id=uuid.UUID(ids["sucursal_id"]),
            numero_orden=numero,
            punto_venta_id=uuid.UUID(ids["punto_venta_id"]),
            canal="pdv",
            modalidad="mesa",
            cliente_id=uuid.UUID(ids["cliente_id"]) if con_cliente else None,
            usuario_id=s.scalar(select(Usuario.id).where(Usuario.username == "admin")),
            estado="pagada",
            total=Decimal("50.00"),
            idempotency_key=f"venta-mkt-{numero}",
        )
        s.add(venta)
        s.flush()
        s.add(
            VentaItem(
                venta_id=venta.id,
                producto_comercial_id=uuid.UUID(ids["producto_id"]),
                cantidad=Decimal(1),
                precio_unitario=Decimal("50.00"),
                estado_preparacion="entregado" if entregada else "listo",
            )
        )
        s.commit()
        return str(venta.id)


# --- Campaña ---------------------------------------------------------------


def test_campana_sin_brief_completo_no_se_aprueba(env):
    client, ids, _ = env
    h = _token(client)
    campana = _crear_campana(client, h, ids, con_brief=False)
    assert campana.status_code == 201
    assert campana.json()["estado"] == "brief"

    r = client.post(
        f"/api/v1/marketing/campanas/{campana.json()['id']}/aprobacion", headers=h
    )
    assert r.status_code == 409
    assert "brief incompleto" in r.json()["detail"]


def test_campana_brief_completado_por_parches_se_aprueba_y_lanza(env):
    client, ids, _ = env
    h = _token(client)
    campana_id = _crear_campana(client, h, ids, con_brief=False).json()["id"]

    parche = client.patch(
        f"/api/v1/marketing/campanas/{campana_id}/brief",
        headers=h,
        json={
            "objetivo": "Notoriedad de la nueva carta",
            "publico_objetivo": "Vecinos de Castilla",
            "presupuesto": "1500.00",
            "kpi": "alcance",
        },
    )
    assert parche.status_code == 200

    lanzada = _lanzar(client, h, campana_id)
    assert lanzada.status_code == 200
    assert lanzada.json()["estado"] == "en_curso"


def test_campana_sin_aprobar_no_sale_a_canal(env):
    client, ids, _ = env
    h = _token(client)
    campana_id = _crear_campana(client, h, ids).json()["id"]
    r = client.post(f"/api/v1/marketing/campanas/{campana_id}/lanzamiento", headers=h)
    assert r.status_code == 409


def test_crear_campana_es_idempotente(env):
    client, ids, _ = env
    h = _token(client)
    primera = _crear_campana(client, h, ids, key="mkt-idem")
    segunda = _crear_campana(client, h, ids, key="mkt-idem")
    assert primera.json()["id"] == segunda.json()["id"]


def test_implementacion_incompleta_exige_incidencia(env):
    client, ids, _ = env
    h = _token(client)
    campana_id = _crear_campana(client, h, ids).json()["id"]
    _lanzar(client, h, campana_id)

    sin_incidencia = client.post(
        f"/api/v1/marketing/campanas/{campana_id}/implementaciones",
        headers=h,
        json={"sucursal_id": ids["sucursal_id"], "completa": False},
    )
    assert sin_incidencia.status_code == 409

    con_incidencia = client.post(
        f"/api/v1/marketing/campanas/{campana_id}/implementaciones",
        headers=h,
        json={
            "sucursal_id": ids["sucursal_id"],
            "completa": False,
            "incidencia": "Faltó el afiche del producto clásico",
        },
    )
    assert con_incidencia.status_code == 201


# --- Contenido -------------------------------------------------------------


def test_pieza_no_pertinente_no_se_publica(env):
    client, ids, _ = env
    h = _token(client)
    pieza = client.post(
        "/api/v1/marketing/piezas",
        headers=h,
        json={
            "marca_id": ids["marca_id"],
            "titulo": "Meme viral del momento",
            "canal": "tiktok",
            "fecha_publicacion": str(fechas.hoy()),
            "uso_marca_validado": True,
        },
    )
    assert pieza.status_code == 201
    pieza_id = pieza.json()["id"]

    bloqueada = client.post(
        f"/api/v1/marketing/piezas/{pieza_id}/publicacion", headers=h, json={}
    )
    assert bloqueada.status_code == 409

    client.patch(
        f"/api/v1/marketing/piezas/{pieza_id}/validacion",
        headers=h,
        json={"pertinente_marca": True},
    )
    publicada = client.post(
        f"/api/v1/marketing/piezas/{pieza_id}/publicacion",
        headers=h,
        json={"metricas": {"alcance": 12000}},
    )
    assert publicada.status_code == 200
    assert publicada.json()["estado"] == "publicada"
    assert publicada.json()["metricas"] == {"alcance": 12000}


# --- Lead ------------------------------------------------------------------


def test_campana_en_brief_no_genera_leads(env):
    client, ids, _ = env
    h = _token(client)
    campana_id = _crear_campana(client, h, ids).json()["id"]
    r = client.post(
        "/api/v1/marketing/leads",
        headers=h,
        json={
            "campana_id": campana_id,
            "canal": "instagram",
            "tipo": "contacto",
            "idempotency_key": "lead-en-brief",
        },
    )
    assert r.status_code == 409


def test_lead_se_atribuye_a_la_venta_a_mano(env):
    client, ids, TestSession = env
    h = _token(client)
    campana_id = _crear_campana(client, h, ids).json()["id"]
    _lanzar(client, h, campana_id)

    lead = client.post(
        "/api/v1/marketing/leads",
        headers=h,
        json={
            "campana_id": campana_id,
            "canal": "instagram",
            "tipo": "cupon",
            "cliente_id": ids["cliente_id"],
            "idempotency_key": "lead-manual",
        },
    )
    assert lead.status_code == 201
    venta_id = _venta(TestSession, ids, entregada=False, numero=10)

    atribuido = client.post(
        f"/api/v1/marketing/leads/{lead.json()['id']}/atribucion",
        headers=h,
        json={"venta_id": venta_id},
    )
    assert atribuido.status_code == 200
    assert atribuido.json()["venta_id"] == venta_id

    repetido = client.post(
        f"/api/v1/marketing/leads/{lead.json()['id']}/atribucion",
        headers=h,
        json={"venta_id": venta_id},
    )
    assert repetido.status_code == 409


def test_atribucion_automatica_solo_sin_ambiguedad(env):
    client, ids, TestSession = env
    h = _token(client)
    campana_id = _crear_campana(client, h, ids).json()["id"]
    _lanzar(client, h, campana_id)

    def _lead(key):
        return client.post(
            "/api/v1/marketing/leads",
            headers=h,
            json={
                "campana_id": campana_id,
                "canal": "instagram",
                "tipo": "registro",
                "cliente_id": ids["cliente_id"],
                "idempotency_key": key,
            },
        ).json()["id"]

    unico = _lead("lead-auto-1")
    # La venta se siembra de verdad: `lead.venta_id` es FK y con un UUID
    # inventado el UPDATE del listener no pasa contra Postgres.
    listeners.on_venta_confirmada(
        {
            "venta_id": _venta(TestSession, ids, entregada=False, numero=30),
            "cliente_id": ids["cliente_id"],
        }
    )
    with TestSession() as s:
        assert s.get(Lead, uuid.UUID(unico)).venta_id is not None

    # Dos leads abiertos del mismo cliente: adivinar cuál convirtió falsearía
    # la medición, así que ninguno se atribuye solo.
    segundo = _lead("lead-auto-2")
    tercero = _lead("lead-auto-3")
    listeners.on_venta_confirmada(
        {
            "venta_id": _venta(TestSession, ids, entregada=False, numero=31),
            "cliente_id": ids["cliente_id"],
        }
    )
    with TestSession() as s:
        assert s.get(Lead, uuid.UUID(segundo)).venta_id is None
        assert s.get(Lead, uuid.UUID(tercero)).venta_id is None


# --- Encuesta --------------------------------------------------------------


def test_encuesta_exige_pedido_entregado(env):
    client, ids, TestSession = env
    h = _token(client)
    venta_id = _venta(TestSession, ids, entregada=False, numero=20)
    r = client.post(
        "/api/v1/marketing/encuestas",
        headers=h,
        json={"venta_id": venta_id, "canal": "whatsapp"},
    )
    assert r.status_code == 409


def test_encuesta_exige_cliente_registrado(env):
    client, ids, TestSession = env
    h = _token(client)
    venta_id = _venta(TestSession, ids, entregada=True, con_cliente=False, numero=21)
    r = client.post(
        "/api/v1/marketing/encuestas",
        headers=h,
        json={"venta_id": venta_id, "canal": "link"},
    )
    assert r.status_code == 409


def test_encuesta_se_envia_una_sola_vez_y_se_responde(env):
    client, ids, TestSession = env
    h = _token(client)
    venta_id = _venta(TestSession, ids, entregada=True, numero=22)

    enviada = client.post(
        "/api/v1/marketing/encuestas",
        headers=h,
        json={"venta_id": venta_id, "canal": "whatsapp"},
    )
    assert enviada.status_code == 201
    cuerpo = enviada.json()
    assert cuerpo["encuesta"]["estado"] == "enviada"
    # Nace parada en el primer nodo del guion, no esperando "un puntaje".
    assert cuerpo["pregunta_actual"]["codigo"] == "puntaje"

    reenvio = client.post(
        "/api/v1/marketing/encuestas",
        headers=h,
        json={"venta_id": venta_id, "canal": "pos"},
    )
    assert reenvio.json()["encuesta"]["id"] == cuerpo["encuesta"]["id"]

    encuesta_id = cuerpo["encuesta"]["id"]

    def responder(valor):
        return client.post(
            f"/api/v1/marketing/encuestas/{encuesta_id}/respuesta",
            headers=h,
            json={"valor": valor},
        )

    # 5 estrellas ⇒ rama "¿nos recomendarías?", no la de "¿qué falló?".
    paso = responder("5")
    assert paso.status_code == 200
    assert paso.json()["pregunta_actual"]["codigo"] == "recomendaria"

    paso = responder("Sí")  # se normaliza a "si"
    assert paso.json()["pregunta_actual"]["codigo"] == "comentario"

    respondida = responder("Todo bien")
    assert respondida.json()["encuesta"]["estado"] == "respondida"
    assert respondida.json()["encuesta"]["puntaje"] == 5
    assert respondida.json()["encuesta"]["comentario"] == "Todo bien"
    assert respondida.json()["pregunta_actual"] is None

    assert responder("3").status_code == 409


# --- Alcance de tenant (ADR-004) -------------------------------------------


def test_campana_de_otra_empresa_no_es_visible(env):
    client, ids, TestSession = env
    h = _token(client)
    campana_id = _crear_campana(client, h, ids).json()["id"]

    with TestSession() as s:
        from src.modules.marketing.infrastructure.models import Campana

        otra = Empresa(
            grupo_id=s.scalar(select(Marca.grupo_id)),
            ruc="20999999999",
            razon_social="Otra SAC",
            domicilio_fiscal="Otra dirección",
            tipo="operativa",
        )
        s.add(otra)
        s.flush()
        s.get(Campana, uuid.UUID(campana_id)).empresa_id = otra.id
        s.commit()

    mkt = _token(client, username="mkt1", pin="111111")
    assert client.get(f"/api/v1/marketing/campanas/{campana_id}", headers=mkt).status_code == 403
    assert client.get("/api/v1/marketing/campanas", headers=mkt).json()["items"] == []


def test_listar_piezas_del_tenant_y_por_estado(env):
    """Sin listado no había forma de ver el calendario de contenido: la
    pieza solo se consultaba sabiendo su id."""
    client, ids, _ = env
    h = _token(client)
    campana_id = _crear_campana(client, h, ids, key="mkt-piezas-1").json()["id"]
    for titulo, campana in (("Post de campaña", campana_id), ("Post siempre-verde", None)):
        r = client.post(
            "/api/v1/marketing/piezas",
            headers=h,
            json={
                "marca_id": ids["marca_id"],
                "titulo": titulo,
                "canal": "instagram",
                "fecha_publicacion": str(fechas.hoy()),
                "campana_id": campana,
                "pertinente_marca": True,
                "uso_marca_validado": True,
            },
        )
        assert r.status_code == 201

    listado = client.get("/api/v1/marketing/piezas", headers=h).json()
    assert listado["total"] == 2
    # Ninguna publicada todavía: el filtro por estado no las trae.
    assert client.get(
        "/api/v1/marketing/piezas?estado=publicada", headers=h
    ).json()["total"] == 0
