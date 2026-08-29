"""Tests del slice inventory core: catálogo, stock/movimientos y ajuste
(segregación de funciones). SQLite en memoria + override de get_db.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.app import create_app
from src.core.database import Base
from src.core.events import event_bus
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    Sku,
    UnidadMedida,
)
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Marca,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
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
        udm_cat = CategoriaUdm(nombre="Peso")
        s.add(udm_cat)
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo", ratio=Decimal(1))
        almacen = Almacen(empresa_id=empresa.id, nombre="Central", tipo="central")
        art = Articulo(
            empresa_id=empresa.id, id_interno="H001", nombre="Harina",
            unidad_medida_id=None, tipo="insumo",
        )
        s.add_all([udm, almacen])
        s.flush()
        art.unidad_medida_id = udm.id
        s.add(art)
        s.flush()
        sku = Sku(articulo_id=art.id, codigo="SKU-HARINA")
        s.add(sku)
        s.flush()
        # Segundo usuario con rol almacenero (permiso inventory.solicitar_ajuste).
        # Va asignado a una sucursal: sin ella el JWT no lleva empresa y el
        # contexto de tenant (ADR-004) le niega todo.
        marca = s.scalar(select(Marca))
        sucursal = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre="Tarapoto Centro",
            direccion="Jr. X 123", tenencia="alquilada",
        )
        almacenero = Usuario(
            username="almacenero1", pin_hash=hash_pin("654321"), tipo="humano",
        )
        s.add_all([sucursal, almacenero])
        s.flush()
        rol_alm = s.scalar(select(Rol).where(Rol.nombre == "almacenero"))
        s.add_all([
            UsuarioRol(usuario_id=almacenero.id, rol_id=rol_alm.id),
            UsuarioSucursal(usuario_id=almacenero.id, sucursal_id=sucursal.id),
        ])
        ids.update(
            empresa_id=str(empresa.id), udm_id=str(udm.id),
            almacen_id=str(almacen.id), articulo_id=str(art.id), sku_id=str(sku.id),
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


def test_crear_articulo_y_sku(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/inventory/articulos", headers=h, json={
        "empresa_id": ids["empresa_id"], "id_interno": "Q001", "nombre": "Queso",
        "unidad_medida_id": ids["udm_id"], "tipo": "insumo",
    })
    assert r.status_code == 201
    art_id = r.json()["id"]
    r2 = client.post("/api/v1/inventory/skus", headers=h, json={
        "articulo_id": art_id, "codigo": "SKU-QUESO",
    })
    assert r2.status_code == 201


def test_id_interno_duplicado_409(env):
    client, ids, _ = env
    h = _token(client)
    body = {
        "empresa_id": ids["empresa_id"], "id_interno": "H001", "nombre": "Otra",
        "unidad_medida_id": ids["udm_id"], "tipo": "insumo",
    }
    assert client.post("/api/v1/inventory/articulos", headers=h, json=body).status_code == 409


def test_editar_articulo_corrige_id_interno(env):
    """El código de 4 caracteres es lo que el almacenero lee en el estante:
    tecleado mal se arrastra por toda la operación, y era inmutable."""
    client, ids, _ = env
    h = _token(client)
    art_id = client.post("/api/v1/inventory/articulos", headers=h, json={
        "empresa_id": ids["empresa_id"], "id_interno": "Q001", "nombre": "Queso",
        "unidad_medida_id": ids["udm_id"], "tipo": "insumo",
    }).json()["id"]

    r = client.patch(
        f"/api/v1/inventory/articulos/{art_id}",
        headers=h,
        json={"id_interno": "Q010", "nombre": "queso edam"},
    )
    assert r.status_code == 200
    assert r.json()["id_interno"] == "Q010"
    # `a_titulo` sigue aplicándose al nombre, igual que en el alta.
    assert r.json()["nombre"] == "Queso Edam"


def test_editar_articulo_id_interno_duplicado_409(env):
    client, ids, _ = env
    h = _token(client)
    art_id = client.post("/api/v1/inventory/articulos", headers=h, json={
        "empresa_id": ids["empresa_id"], "id_interno": "Q001", "nombre": "Queso",
        "unidad_medida_id": ids["udm_id"], "tipo": "insumo",
    }).json()["id"]

    r = client.patch(
        f"/api/v1/inventory/articulos/{art_id}", headers=h, json={"id_interno": "H001"}
    )
    assert r.status_code == 409


def test_editar_articulo_conserva_su_propio_id_interno(env):
    """Reenviar el mismo código no puede chocar consigo mismo: el formulario
    manda todos sus campos siempre, no solo los que cambiaron."""
    client, ids, _ = env
    h = _token(client)
    art_id = client.post("/api/v1/inventory/articulos", headers=h, json={
        "empresa_id": ids["empresa_id"], "id_interno": "Q001", "nombre": "Queso",
        "unidad_medida_id": ids["udm_id"], "tipo": "insumo",
    }).json()["id"]

    r = client.patch(
        f"/api/v1/inventory/articulos/{art_id}",
        headers=h,
        json={"id_interno": "Q001", "nombre": "Queso Fresco"},
    )
    assert r.status_code == 200


def test_editar_articulo_categoria_inexistente_404(env):
    client, ids, _ = env
    h = _token(client)
    art_id = client.post("/api/v1/inventory/articulos", headers=h, json={
        "empresa_id": ids["empresa_id"], "id_interno": "Q001", "nombre": "Queso",
        "unidad_medida_id": ids["udm_id"], "tipo": "insumo",
    }).json()["id"]

    r = client.patch(
        f"/api/v1/inventory/articulos/{art_id}",
        headers=h,
        json={"categoria_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 404


def test_movimiento_actualiza_stock(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/inventory/movimientos", headers=h, json={
        "almacen_id": ids["almacen_id"], "sku_id": ids["sku_id"],
        "cantidad": "100", "tipo": "recepcion_compra",
    })
    assert r.status_code == 201
    stock = client.get(
        f"/api/v1/inventory/stock?almacen_id={ids['almacen_id']}", headers=h
    ).json()["items"]
    assert len(stock) == 1
    assert Decimal(stock[0]["cantidad"]) == Decimal("100")


def test_salida_mayor_que_stock_409(env):
    client, ids, _ = env
    h = _token(client)
    client.post("/api/v1/inventory/movimientos", headers=h, json={
        "almacen_id": ids["almacen_id"], "sku_id": ids["sku_id"],
        "cantidad": "10", "tipo": "recepcion_compra",
    })
    r = client.post("/api/v1/inventory/movimientos", headers=h, json={
        "almacen_id": ids["almacen_id"], "sku_id": ids["sku_id"],
        "cantidad": "-50", "tipo": "consumo_venta",
    })
    assert r.status_code == 409


def test_ajuste_mismo_usuario_no_aprueba(env):
    client, ids, _ = env
    h = _token(client)  # admin (tiene solicitar y aprobar vía *)
    aj = client.post("/api/v1/inventory/ajustes", headers=h, json={
        "almacen_id": ids["almacen_id"], "sku_id": ids["sku_id"],
        "cantidad": "5", "motivo": "sobrante",
    }).json()
    r = client.post(f"/api/v1/inventory/ajustes/{aj['id']}/aprobar", headers=h)
    assert r.status_code == 409  # aprobador == solicitante


def test_ajuste_flujo_segregado_ok(env):
    client, ids, _ = env
    h_alm = _token(client, "almacenero1", "654321")
    h_admin = _token(client)
    aj = client.post("/api/v1/inventory/ajustes", headers=h_alm, json={
        "almacen_id": ids["almacen_id"], "sku_id": ids["sku_id"],
        "cantidad": "7", "motivo": "sobrante",
    })
    assert aj.status_code == 201
    r = client.post(
        f"/api/v1/inventory/ajustes/{aj.json()['id']}/aprobar", headers=h_admin
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "aprobado"
    stock = client.get(
        f"/api/v1/inventory/stock?almacen_id={ids['almacen_id']}", headers=h_admin
    ).json()["items"]
    assert Decimal(stock[0]["cantidad"]) == Decimal("7")


def test_stock_bajo_minimo_flag(env):
    client, ids, TestSession = env
    h = _token(client)
    client.post("/api/v1/inventory/movimientos", headers=h, json={
        "almacen_id": ids["almacen_id"], "sku_id": ids["sku_id"],
        "cantidad": "3", "tipo": "recepcion_compra",
    })
    # Fija stock_minimo directo (no hay API para ello en este slice).
    from src.modules.inventory.infrastructure.models import Stock
    with TestSession() as s:
        st = s.scalar(select(Stock))
        st.stock_minimo = Decimal("5")
        s.commit()
    stock = client.get("/api/v1/inventory/stock", headers=h).json()["items"]
    assert stock[0]["bajo_minimo"] is True


def test_stock_bajo_minimo_avisa_al_cruzar_una_sola_vez(env):
    """El evento marca el cruce, no el estado: si sonara en cada venta con
    el stock ya bajo, nadie lo miraría cuando importa."""
    client, ids, TestSession = env
    h = _token(client)
    client.post("/api/v1/inventory/movimientos", headers=h, json={
        "almacen_id": ids["almacen_id"], "sku_id": ids["sku_id"],
        "cantidad": "10", "tipo": "recepcion_compra",
    })
    from src.modules.inventory.infrastructure.models import Stock
    with TestSession() as s:
        s.scalar(select(Stock)).stock_minimo = Decimal("5")
        s.commit()

    avisos = []
    event_bus.subscribe("inventory.stock_bajo_minimo", avisos.append)

    def _consumir(cantidad):
        return client.post("/api/v1/inventory/movimientos", headers=h, json={
            "almacen_id": ids["almacen_id"], "sku_id": ids["sku_id"],
            "cantidad": str(-cantidad), "tipo": "consumo_venta",
        })

    assert _consumir(3).status_code == 201  # 10 → 7: sigue sobre el mínimo
    assert avisos == []
    assert _consumir(3).status_code == 201  # 7 → 4: cruza
    assert len(avisos) == 1
    assert avisos[0]["cantidad"] == "4.0000"
    # Quién hizo el movimiento que cruzó el mínimo: es a quien se le pregunta
    # qué pasó antes de salir a comprar.
    assert avisos[0]["usuario_id"] is not None
    assert _consumir(1).status_code == 201  # 4 → 3: ya estaba abajo
    assert len(avisos) == 1


def test_movimiento_signo_invalido_409(env):
    client, ids, _ = env
    h = _token(client)
    # recepción (ingreso) con cantidad negativa → inválido.
    r = client.post("/api/v1/inventory/movimientos", headers=h, json={
        "almacen_id": ids["almacen_id"], "sku_id": ids["sku_id"],
        "cantidad": "-5", "tipo": "recepcion_compra",
    })
    assert r.status_code == 409


def test_ajuste_signo_no_coincide_motivo_409(env):
    client, ids, _ = env
    h = _token(client, "almacenero1", "654321")
    # motivo faltante debería ser negativo; +5 es incoherente.
    r = client.post("/api/v1/inventory/ajustes", headers=h, json={
        "almacen_id": ids["almacen_id"], "sku_id": ids["sku_id"],
        "cantidad": "5", "motivo": "faltante",
    })
    assert r.status_code == 409


def test_crear_articulo_udm_inexistente_404(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/inventory/articulos", headers=h, json={
        "empresa_id": ids["empresa_id"], "id_interno": "X001", "nombre": "Fantasma",
        "unidad_medida_id": "00000000-0000-0000-0000-000000000000", "tipo": "insumo",
    })
    assert r.status_code == 404


def test_los_destinos_de_un_reporte_devuelven_el_dato_completo(env):
    """Un reporte que enlaza a una pantalla que no existe sigue siendo una
    línea de texto. Estos GET son el otro extremo del enlace."""
    client, ids, _ = env
    h = _token(client)
    client.post("/api/v1/inventory/movimientos", headers=h, json={
        "almacen_id": ids["almacen_id"], "sku_id": ids["sku_id"],
        "cantidad": "12", "tipo": "recepcion_compra",
    })

    art = client.get(f"/api/v1/inventory/articulos/{ids['articulo_id']}", headers=h)
    assert art.status_code == 200
    assert art.json()["nombre"] == "Harina"

    sku = client.get(f"/api/v1/inventory/skus/{ids['sku_id']}", headers=h)
    assert sku.status_code == 200
    cuerpo = sku.json()
    # Artículo y saldo por almacén en una sola respuesta: la pantalla de
    # "stock bajo mínimo" no puede necesitar tres viajes para decidir.
    assert cuerpo["articulo"]["nombre"] == "Harina"
    assert cuerpo["stock"][0]["almacen"] == "Central"
    assert Decimal(cuerpo["stock"][0]["cantidad"]) == Decimal("12")


def test_listar_articulos_filtra_por_tipo(env):
    """El filtro vive en la base y no en la pantalla porque la lista viene
    paginada: quien solo quiere empaques y filtra lo que le llegó se queda
    sin ninguno en cuanto el catálogo pasa de una página."""
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/inventory/articulos", headers=h, json={
        "id_interno": "A900", "nombre": "Caja Pizza Familiar",
        "unidad_medida_id": ids["udm_id"], "tipo": "empaque",
    })
    assert r.status_code == 201, r.text

    empaques = client.get("/api/v1/inventory/articulos?tipo=empaque", headers=h)
    assert empaques.status_code == 200
    nombres = [a["nombre"] for a in empaques.json()["items"]]
    assert nombres == ["Caja Pizza Familiar"]

    # Sin el filtro sigue viniendo todo: el parámetro es opcional y nadie más
    # tiene que cambiar por esto.
    todos = client.get("/api/v1/inventory/articulos", headers=h)
    assert "Harina" in [a["nombre"] for a in todos.json()["items"]]


def test_listar_articulos_acepta_varios_tipos(env):
    """"Qué se puede producir" son las subrecetas **y** la mercadería. Con un
    solo `tipo` por petición, la pantalla resolvía ese "o" filtrando lo que le
    había llegado de la primera página —cincuenta filas de un catálogo de
    miles—, así que la lista salía casi vacía sin decir por qué."""
    client, ids, _ = env
    h = _token(client)
    for id_interno, nombre, tipo in (
        ("A902", "Caja E2E", "empaque"),
        ("A903", "Masa E2E", "subreceta"),
    ):
        r = client.post("/api/v1/inventory/articulos", headers=h, json={
            "id_interno": id_interno, "nombre": nombre,
            "unidad_medida_id": ids["udm_id"], "tipo": tipo,
        })
        assert r.status_code == 201, r.text

    varios = client.get(
        "/api/v1/inventory/articulos?tipo=empaque&tipo=subreceta", headers=h
    )
    assert varios.status_code == 200
    assert {a["nombre"] for a in varios.json()["items"]} == {"Caja E2E", "Masa E2E"}

    # Un solo `tipo` sigue funcionando igual: el parámetro no cambió de forma
    # para quien ya lo usaba.
    uno = client.get("/api/v1/inventory/articulos?tipo=empaque", headers=h)
    assert [a["nombre"] for a in uno.json()["items"]] == ["Caja E2E"]


def test_listar_articulos_busca_por_nombre_y_codigo(env):
    """La búsqueda vive en la base por la misma razón que el filtro por tipo,
    pero acá aprieta más: con miles de artículos y un techo de 200 filas por
    página, un desplegable que filtre lo que ya recibió deja invisible casi
    todo el catálogo y no avisa — parece que el artículo no existe."""
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/inventory/articulos", headers=h, json={
        "id_interno": "A901", "nombre": "Caja Pizza Familiar",
        "unidad_medida_id": ids["udm_id"], "tipo": "empaque",
    })
    assert r.status_code == 201, r.text

    por_nombre = client.get("/api/v1/inventory/articulos?q=pizza", headers=h)
    assert por_nombre.status_code == 200
    assert [a["nombre"] for a in por_nombre.json()["items"]] == ["Caja Pizza Familiar"]

    # Por código interno: quien lo tiene a mano lo teclea en vez del nombre.
    por_codigo = client.get("/api/v1/inventory/articulos?q=A901", headers=h)
    assert [a["nombre"] for a in por_codigo.json()["items"]] == ["Caja Pizza Familiar"]

    # Insensible a mayúsculas, y sin resultados devuelve la lista vacía —no un
    # error: "no encontré nada" es una respuesta válida para un buscador.
    assert por_nombre.json()["items"] == client.get(
        "/api/v1/inventory/articulos?q=PIZZA", headers=h
    ).json()["items"]
    assert client.get("/api/v1/inventory/articulos?q=zzz", headers=h).json()["items"] == []

    # Se combina con `tipo`, y sin el parámetro sigue viniendo todo.
    assert client.get(
        "/api/v1/inventory/articulos?q=pizza&tipo=insumo", headers=h
    ).json()["items"] == []
    assert "Harina" in [
        a["nombre"]
        for a in client.get("/api/v1/inventory/articulos", headers=h).json()["items"]
    ]


def test_ajustes_se_pueden_listar_y_abrir(env):
    """Antes solo se podían crear y aprobar: `inventory.ajuste_fuera_margen`
    reportaba un hecho que no se podía ir a mirar."""
    client, ids, _ = env
    h = _token(client)
    h_alm = _token(client, "almacenero1", "654321")
    creado = client.post("/api/v1/inventory/ajustes", headers=h_alm, json={
        "almacen_id": ids["almacen_id"], "sku_id": ids["sku_id"],
        "cantidad": "-3", "motivo": "merma",
    })
    assert creado.status_code == 201, creado.text

    lista = client.get("/api/v1/inventory/ajustes?estado=pendiente", headers=h)
    assert lista.status_code == 200
    assert [a["id"] for a in lista.json()["items"]] == [creado.json()["id"]]

    detalle = client.get(
        f"/api/v1/inventory/ajustes/{creado.json()['id']}", headers=h
    ).json()
    assert detalle["articulo"] == "Harina"
    assert detalle["sku_codigo"] == "SKU-HARINA"
    assert detalle["almacen"] == "Central"
    assert detalle["solicitante"] == "almacenero1"
    assert detalle["aprobador"] is None


def test_un_destino_inexistente_responde_404(env):
    client, _, _ = env
    h = _token(client)
    fantasma = "00000000-0000-0000-0000-000000000000"
    for recurso in ("articulos", "skus", "lotes", "categorias", "ajustes"):
        r = client.get(f"/api/v1/inventory/{recurso}/{fantasma}", headers=h)
        assert r.status_code == 404, recurso


def test_contar_incidencias_recientes(env):
    import uuid as uuid_mod

    from src.modules.inventory.application.queries_publicas import (
        contar_incidencias_recientes,
    )
    from src.modules.inventory.infrastructure.models import IncidenciaInventario

    client, ids, TestSession = env
    with TestSession() as s:
        s.add(
            IncidenciaInventario(
                empresa_id=uuid_mod.UUID(ids["empresa_id"]),
                origen="venta",
                referencia="venta-1",
                tipo="sin_sku",
                detalle="artículo sin SKU activo",
            )
        )
        s.commit()

    with TestSession() as s:
        n = contar_incidencias_recientes(s, uuid_mod.UUID(ids["empresa_id"]))
    assert n == 1


def test_leer_sin_permiso_403(env):
    client, ids, _ = env
    h = _token(client, "almacenero1", "654321")  # tiene inventory.leer
    assert client.get("/api/v1/inventory/stock", headers=h).status_code == 200
    # crear_categoria exige gestionar_catalogo, que almacenero no tiene.
    r = client.post("/api/v1/inventory/categorias", headers=h, json={
        "empresa_id": ids["empresa_id"], "nombre": "Lácteos",
    })
    assert r.status_code == 403
