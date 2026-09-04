"""La cuenta contable se configura en la categoría y se hereda (ADR-086).

Hasta este cambio, `plantillas.py` escribía todo producto contra los mismos
códigos: toda venta acreditaba `7011` y toda compra debitaba `6011` y `201`.
Un restaurante que compra insumos, empaques y **servicios** los mandaba a la
misma cuenta, y el alquiler terminaba en existencias.

Lo que se afirma acá, en este orden:

1. **Sin configurar nada, nada cambia.** Es la propiedad que hace el cambio
   desplegable: los casos de `test_accounting_pcge.py` que afirman el asiento
   de fábrica siguen verdes sin tocarlos, y acá se afirma explícitamente.
2. La herencia por el árbol de categorías.
3. El reparto, que tiene que cuadrar **al céntimo** contra la línea de
   contraparte, que no se reparte.
4. Que una configuración con un dedazo no rompe la operación: cae al código
   de fábrica.
5. Los servicios, que no entran a existencias.
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
from src.modules.accounting.application import asientos as asientos_uc
from src.modules.accounting.application import listeners as accounting_listeners
from src.modules.accounting.application.queries_publicas import roles_contables
from src.modules.accounting.domain import plantillas
from src.modules.inventory.application import listeners as inventory_listeners
from src.modules.inventory.infrastructure.models import (
    Categoria,
    CategoriaUdm,
    UnidadMedida,
)
from src.modules.sales.infrastructure.models import ProductoComercial
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Almacen, Empresa, Marca, Sucursal
from src.shared import fechas


@pytest.fixture()
def env(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(inventory_listeners, "session_factory", TestSession)
    monkeypatch.setattr(accounting_listeners, "session_factory", TestSession)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        marca = s.scalar(select(Marca))
        almacen = Almacen(empresa_id=empresa.id, nombre="Central", tipo="central")
        sucursal = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre="Local 1",
            direccion="Jr. Falso 123", tenencia="propia",
        )
        udm_cat = CategoriaUdm(nombre="Peso")
        s.add_all([almacen, sucursal, udm_cat])
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo", ratio=Decimal(1))
        s.add(udm)
        s.flush()
        ids.update(
            empresa_id=str(empresa.id),
            marca_id=str(marca.id),
            almacen_id=str(almacen.id),
            sucursal_id=str(sucursal.id),
            udm_id=str(udm.id),
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


def _preparar(client, h, ids):
    """Periodo abierto y PCGE importado: sin las dos cosas no hay asiento que
    mirar, y su ausencia no es un error (la generación nunca bloquea)."""
    hoy = fechas.hoy()
    client.post(
        "/api/v1/accounting/periodos", headers=h,
        json={"empresa_id": ids["empresa_id"], "anio": hoy.year, "mes": hoy.month},
    )
    client.post(
        f"/api/v1/accounting/cuentas-contables/pcge?empresa_id={ids['empresa_id']}",
        headers=h,
    )


def _categoria(client, h, ids, nombre, *, config=None, padre_id=None):
    cuerpo = {"empresa_id": ids["empresa_id"], "nombre": nombre}
    if config is not None:
        cuerpo["asiento_contable_config"] = config
    if padre_id is not None:
        cuerpo["padre_id"] = padre_id
    return client.post("/api/v1/inventory/categorias", headers=h, json=cuerpo)


def _articulo(client, h, ids, id_interno, *, categoria_id=None, tipo="insumo"):
    cuerpo = {
        "empresa_id": ids["empresa_id"], "id_interno": id_interno,
        "nombre": f"Artículo {id_interno}", "unidad_medida_id": ids["udm_id"],
        "tipo": tipo,
    }
    if categoria_id:
        cuerpo["categoria_id"] = categoria_id
    return client.post("/api/v1/inventory/articulos", headers=h, json=cuerpo).json()["id"]


def _recibir(ids, items):
    """`purchases.compra_recibida` tal como lo publica el módulo."""
    oc_id = str(uuid.uuid4())
    accounting_listeners.on_compra_recibida(
        {
            "orden_compra_id": oc_id,
            "almacen_destino_id": ids["almacen_id"],
            "items": items,
        }
    )
    return oc_id


def _vender(ids, total, items):
    venta_id = str(uuid.uuid4())
    accounting_listeners.on_venta_confirmada(
        {
            "venta_id": venta_id,
            "sucursal_id": ids["sucursal_id"],
            "items": items,
            "total": total,
        }
    )
    return venta_id


def _lineas(client, h, ids, referencia):
    asientos = client.get(
        f"/api/v1/accounting/asientos?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"]
    generado = [a for a in asientos if a["referencia_origen"] == referencia]
    assert len(generado) == 1, f"se esperaba un asiento para {referencia}"
    detalle = client.get(
        f"/api/v1/accounting/asientos/{generado[0]['id']}/lineas", headers=h
    ).json()
    cuentas = client.get(
        f"/api/v1/accounting/cuentas-contables?empresa_id={ids['empresa_id']}", headers=h
    ).json()
    por_id = {c["id"]: c["codigo"] for c in cuentas}
    return {
        (por_id[linea["cuenta_contable_id"]], linea["tipo"]): Decimal(str(linea["monto"]))
        for linea in detalle
    }


# --- Sin configurar nada, nada cambia ----------------------------------------
def test_sin_configuracion_el_asiento_es_el_de_siempre(env):
    """La propiedad que hace este cambio desplegable. Si alguna vez falla, es
    que el reparto se metió en el camino de fábrica."""
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)
    articulo_id = _articulo(client, h, ids, "S001")

    oc_id = _recibir(
        ids, [{"articulo_id": articulo_id, "cantidad": "10", "costo_unitario": "20.00"}]
    )

    assert _lineas(client, h, ids, oc_id) == {
        ("6011", "debe"): Decimal("200.00"),
        ("4212", "haber"): Decimal("200.00"),
        ("201", "debe"): Decimal("200.00"),
        ("611", "haber"): Decimal("200.00"),
    }


# --- Herencia por el árbol ----------------------------------------------------
def test_la_hija_hereda_la_cuenta_de_su_madre(env):
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)
    madre = _categoria(client, h, ids, "Bebidas", config={"compra": "6021"}).json()
    hija = _categoria(client, h, ids, "Gaseosas", padre_id=madre["id"]).json()
    articulo_id = _articulo(client, h, ids, "H001", categoria_id=hija["id"])

    oc_id = _recibir(
        ids, [{"articulo_id": articulo_id, "cantidad": "1", "costo_unitario": "100.00"}]
    )

    lineas = _lineas(client, h, ids, oc_id)
    assert lineas[("6021", "debe")] == Decimal("100.00")
    assert ("6011", "debe") not in lineas


def test_la_hija_pisa_a_la_madre_rol_por_rol(env):
    """La herencia se completa por rol, no por mapa entero: la hija define su
    cuenta de compra y sigue heredando el destino de la madre."""
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)
    madre = _categoria(
        client, h, ids, "Abarrotes", config={"compra": "6021", "existencia": "202"}
    ).json()
    hija = _categoria(
        client, h, ids, "Enlatados", config={"compra": "6031"}, padre_id=madre["id"]
    ).json()
    articulo_id = _articulo(client, h, ids, "E001", categoria_id=hija["id"])

    oc_id = _recibir(
        ids, [{"articulo_id": articulo_id, "cantidad": "1", "costo_unitario": "50.00"}]
    )

    lineas = _lineas(client, h, ids, oc_id)
    assert lineas[("6031", "debe")] == Decimal("50.00")
    assert lineas[("202", "debe")] == Decimal("50.00")


def test_un_ciclo_escrito_a_mano_no_cuelga_el_asiento(env):
    """`_validar_madre` impide crear el ciclo, pero la base no puede: una fila
    tocada a mano no puede dejar el asiento de una venta girando."""
    client, ids, TestSession = env
    h = _token(client)
    _preparar(client, h, ids)
    una = _categoria(client, h, ids, "Una", config={"compra": "6021"}).json()
    otra = _categoria(client, h, ids, "Otra", padre_id=una["id"]).json()
    with TestSession() as s:
        s.get(Categoria, uuid.UUID(una["id"])).padre_id = uuid.UUID(otra["id"])
        s.commit()
    articulo_id = _articulo(client, h, ids, "C001", categoria_id=otra["id"])

    oc_id = _recibir(
        ids, [{"articulo_id": articulo_id, "cantidad": "1", "costo_unitario": "10.00"}]
    )
    assert _lineas(client, h, ids, oc_id)[("6021", "debe")] == Decimal("10.00")


# --- Reparto ------------------------------------------------------------------
def test_una_compra_de_dos_categorias_reparte_y_cuadra(env):
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)
    bebidas = _categoria(client, h, ids, "Bebidas", config={"compra": "6021"}).json()
    envases = _categoria(client, h, ids, "Envases", config={"compra": "6031"}).json()
    uno = _articulo(client, h, ids, "B001", categoria_id=bebidas["id"])
    otro = _articulo(client, h, ids, "V001", categoria_id=envases["id"])

    oc_id = _recibir(ids, [
        {"articulo_id": uno, "cantidad": "10", "costo_unitario": "20.00"},
        {"articulo_id": otro, "cantidad": "5", "costo_unitario": "10.00"},
    ])

    lineas = _lineas(client, h, ids, oc_id)
    assert lineas[("6021", "debe")] == Decimal("200.00")
    assert lineas[("6031", "debe")] == Decimal("50.00")
    # La contraparte no se reparte: la deuda es del proveedor, no del
    # producto. Y es contra ella que el reparto tiene que cuadrar.
    assert lineas[("4212", "haber")] == Decimal("250.00")
    debe = sum(m for (_, tipo), m in lineas.items() if tipo == "debe")
    haber = sum(m for (_, tipo), m in lineas.items() if tipo == "haber")
    assert debe == haber


def test_el_reparto_no_pierde_un_centimo(env):
    """Tres partes iguales de 100: redondear cada una por su cuenta da 99.99 y
    deja el asiento descuadrado. El residuo va entero a la parte mayor."""
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)
    articulos = []
    for i, codigo in enumerate(("6021", "6031", "6032"), start=1):
        cat = _categoria(client, h, ids, f"Cat {i}", config={"compra": codigo}).json()
        articulos.append(_articulo(client, h, ids, f"R00{i}", categoria_id=cat["id"]))

    oc_id = _recibir(ids, [
        {"articulo_id": a, "cantidad": "1", "costo_unitario": "33.3333333"}
        for a in articulos
    ])

    lineas = _lineas(client, h, ids, oc_id)
    del_elemento_6 = sum(
        m for (codigo, tipo), m in lineas.items() if codigo.startswith("60") and tipo == "debe"
    )
    assert del_elemento_6 == lineas[("4212", "haber")]


def test_dos_categorias_con_la_misma_cuenta_producen_una_sola_linea(env):
    """El mayor no gana nada con la misma cuenta escrita dos veces en el mismo
    asiento."""
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)
    una = _categoria(client, h, ids, "Una", config={"compra": "6021"}).json()
    otra = _categoria(client, h, ids, "Otra", config={"compra": "6021"}).json()
    a = _articulo(client, h, ids, "U001", categoria_id=una["id"])
    b = _articulo(client, h, ids, "O001", categoria_id=otra["id"])

    oc_id = _recibir(ids, [
        {"articulo_id": a, "cantidad": "1", "costo_unitario": "60.00"},
        {"articulo_id": b, "cantidad": "1", "costo_unitario": "40.00"},
    ])

    assert _lineas(client, h, ids, oc_id)[("6021", "debe")] == Decimal("100.00")


def test_el_desglose_es_peso_y_no_importe(env):
    """Un desglose que no suma el monto del evento —un ítem sin categoría, un
    payload parcial, una recepción con costo corregido— no puede cambiar
    cuánto asienta el evento. Es la propiedad que hace que este parámetro no
    sea una vía para descuadrar el mayor.

    Se llama al caso de uso directo: es la única forma de mandar un desglose
    deliberadamente incompleto, que es justo lo que se quiere probar.
    """
    client, ids, TestSession = env
    h = _token(client)
    _preparar(client, h, ids)
    cat = _categoria(client, h, ids, "Bebidas", config={"compra": "6021"}).json()

    with TestSession() as s:
        asiento = asientos_uc.crear_asiento_automatico_si_hay_regla(
            s,
            empresa_id=uuid.UUID(ids["empresa_id"]),
            evento="purchases.compra_recibida",
            fecha=fechas.hoy(),
            glosa="Desglose incompleto",
            referencia_origen="peso-no-importe",
            monto=Decimal("100.00"),
            # 40 de 100: el resto del evento no tiene categoría conocida.
            desglose=[
                {
                    "categoria_id": uuid.UUID(cat["id"]),
                    "es_servicio": False,
                    "monto": Decimal("40.00"),
                }
            ],
        )
        assert asiento is not None
        s.commit()

    lineas = _lineas(client, h, ids, "peso-no-importe")
    assert lineas[("4212", "haber")] == Decimal("100.00")
    assert lineas[("6021", "debe")] == Decimal("100.00")


def test_la_venta_reparte_el_ingreso_por_categoria_del_producto(env):
    client, ids, TestSession = env
    h = _token(client)
    _preparar(client, h, ids)
    cat = _categoria(client, h, ids, "Pizzas", config={"ingreso": "7021"}).json()
    with TestSession() as s:
        producto = ProductoComercial(
            id_interno="PZ01", marca_id=uuid.UUID(ids["marca_id"]), nombre="Pizza",
            categoria_id=uuid.UUID(cat["id"]),
        )
        s.add(producto)
        s.commit()
        producto_id = str(producto.id)

    venta_id = _vender(ids, "118.00", [
        {"producto_comercial_id": producto_id, "importe": "118.00"},
    ])

    lineas = _lineas(client, h, ids, venta_id)
    assert lineas[("7021", "haber")] == Decimal("118.00")
    assert ("7011", "haber") not in lineas


def test_una_venta_sin_producto_en_el_payload_va_entera_a_la_cuenta_de_fabrica(env):
    """El replay de un hub viejo trae el detalle sin `producto_comercial_id`:
    tiene que seguir asentando como siempre y no perderse."""
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)

    venta_id = _vender(ids, "118.00", [{"receta_id": str(uuid.uuid4()), "cantidad": "1"}])

    assert _lineas(client, h, ids, venta_id) == {
        ("1212", "debe"): Decimal("118.00"),
        ("7011", "haber"): Decimal("118.00"),
    }


# --- Configuración inválida ---------------------------------------------------
@pytest.mark.parametrize(
    "config,fragmento",
    [
        ({"compra": "99999"}, "no existe"),
        ({"compra": "60"}, "agrupa a otras"),
        ({"inventado": "6011"}, None),
    ],
)
def test_una_cuenta_mal_configurada_no_se_guarda(env, config, fragmento):
    """Se comprueba al guardar y no al asentar: un dedazo que se descubre
    cerrando el mes ya contaminó un mes de asientos."""
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)

    r = _categoria(client, h, ids, "Mala", config=config)
    # 409 para la regla de negocio (la cuenta existe o no en ESTA empresa);
    # 422 para el rol que el esquema ni conoce.
    assert r.status_code in (409, 422)
    if fragmento:
        assert fragmento in r.json()["detail"]


def test_una_cuenta_borrada_despues_cae_al_codigo_de_fabrica(env):
    """La validación al guardar es la primera barrera; esta es la segunda. Una
    cuenta que se desactivó después no puede dejar a la empresa sin poder
    comprar."""
    client, ids, TestSession = env
    h = _token(client)
    _preparar(client, h, ids)
    cat = _categoria(client, h, ids, "Bebidas", config={"compra": "6021"}).json()
    articulo_id = _articulo(client, h, ids, "D001", categoria_id=cat["id"])

    from src.modules.accounting.infrastructure.models import CuentaContable
    with TestSession() as s:
        cuenta = s.scalar(
            select(CuentaContable).where(CuentaContable.codigo == "6021")
        )
        s.delete(cuenta)
        s.commit()

    oc_id = _recibir(
        ids, [{"articulo_id": articulo_id, "cantidad": "1", "costo_unitario": "10.00"}]
    )
    assert _lineas(client, h, ids, oc_id)[("6011", "debe")] == Decimal("10.00")


# --- Servicios ----------------------------------------------------------------
def test_la_compra_de_un_servicio_va_a_63_y_no_a_existencias(env):
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)
    cat = _categoria(client, h, ids, "Energía", config={"servicio": "6361"}).json()
    articulo_id = _articulo(
        client, h, ids, "L001", categoria_id=cat["id"], tipo="servicio"
    )

    oc_id = _recibir(
        ids, [{"articulo_id": articulo_id, "cantidad": "1", "costo_unitario": "300.00"}]
    )

    assert _lineas(client, h, ids, oc_id) == {
        ("6361", "debe"): Decimal("300.00"),
        ("4212", "haber"): Decimal("300.00"),
    }


def test_una_compra_mixta_asienta_el_destino_solo_por_lo_inventariable(env):
    """El flete de la misma OC no entra al almacén; la mercadería sí. Y el
    asiento cuadra igual, porque el bloque de destino es un débito y un
    crédito del mismo importe."""
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)
    insumos = _categoria(client, h, ids, "Insumos").json()
    fletes = _categoria(client, h, ids, "Fletes", config={"servicio": "6311"}).json()
    mercaderia = _articulo(client, h, ids, "M001", categoria_id=insumos["id"])
    flete = _articulo(client, h, ids, "F001", categoria_id=fletes["id"], tipo="servicio")

    oc_id = _recibir(ids, [
        {"articulo_id": mercaderia, "cantidad": "1", "costo_unitario": "800.00"},
        {"articulo_id": flete, "cantidad": "1", "costo_unitario": "200.00"},
    ])

    lineas = _lineas(client, h, ids, oc_id)
    assert lineas[("6011", "debe")] == Decimal("800.00")
    assert lineas[("6311", "debe")] == Decimal("200.00")
    assert lineas[("4212", "haber")] == Decimal("1000.00")
    # El destino, solo por lo que sí entró al almacén.
    assert lineas[("201", "debe")] == Decimal("800.00")
    assert lineas[("611", "haber")] == Decimal("800.00")
    debe = sum(m for (_, tipo), m in lineas.items() if tipo == "debe")
    haber = sum(m for (_, tipo), m in lineas.items() if tipo == "haber")
    assert debe == haber


def test_un_servicio_sin_categoria_configurada_va_a_la_cuenta_generica(env):
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)
    articulo_id = _articulo(client, h, ids, "G001", tipo="servicio")

    oc_id = _recibir(
        ids, [{"articulo_id": articulo_id, "cantidad": "1", "costo_unitario": "75.00"}]
    )

    lineas = _lineas(client, h, ids, oc_id)
    assert lineas[(plantillas.CODIGO_SERVICIO_DE_FABRICA, "debe")] == Decimal("75.00")
    assert ("201", "debe") not in lineas


def test_un_servicio_no_deja_incidencia_de_sin_sku(env):
    """Un servicio no tiene SKU porque no tiene existencias, no porque falte
    configurarlo. Sin esto, cada factura de luz dejaba una incidencia que
    alguien tenía que revisar y descartar."""
    client, ids, TestSession = env
    h = _token(client)
    articulo_id = _articulo(client, h, ids, "N001", tipo="servicio")

    inventory_listeners.on_compra_recibida({
        "orden_compra_id": str(uuid.uuid4()),
        "almacen_destino_id": ids["almacen_id"],
        "items": [{"articulo_id": articulo_id, "cantidad": "1", "costo_unitario": "10.00"}],
    })

    from src.modules.inventory.infrastructure.models import IncidenciaInventario
    with TestSession() as s:
        assert s.scalars(select(IncidenciaInventario)).all() == []


def test_un_insumo_sin_sku_activo_sigue_dejando_su_incidencia(env):
    """La contracara: lo que sí debía tener SKU y no lo tiene sigue siendo un
    problema que hay que ver.

    Desde que todo artículo nace con el suyo (RN-PRD-006) el caso ya no se
    arma dándolo de alta y punto: queda el SKU dado de baja, que es el que
    `_sku_de_articulo` sigue descartando por `activo`.
    """
    client, ids, TestSession = env
    h = _token(client)
    articulo_id = _articulo(client, h, ids, "I001")
    from src.modules.inventory.infrastructure.models import Sku
    with TestSession() as s:
        sku = s.scalar(select(Sku).where(Sku.articulo_id == uuid.UUID(articulo_id)))
        sku.activo = False
        s.commit()

    inventory_listeners.on_compra_recibida({
        "orden_compra_id": str(uuid.uuid4()),
        "almacen_destino_id": ids["almacen_id"],
        "items": [{"articulo_id": articulo_id, "cantidad": "1", "costo_unitario": "10.00"}],
    })

    from src.modules.inventory.infrastructure.models import IncidenciaInventario
    with TestSession() as s:
        incidencias = s.scalars(select(IncidenciaInventario)).all()
    assert [i.tipo for i in incidencias] == ["sin_sku"]


# --- Coherencia entre el vocabulario y el formulario ---------------------------
def test_los_roles_del_schema_son_los_del_catalogo_de_accounting():
    """Un rol en el formulario que ninguna plantilla usa sería configuración
    muda; uno en las plantillas que el formulario no ofrece, inalcanzable."""
    from src.modules.inventory.api.schemas import AsientoContableConfig

    assert set(AsientoContableConfig.model_fields) == set(roles_contables())


def test_toda_linea_con_rol_apunta_a_un_rol_del_catalogo():
    for evento, plantilla in plantillas.PLANTILLAS.items():
        for linea in plantilla.lineas:
            assert linea.rol is None or linea.rol in plantillas.ROLES, (
                f"{evento} usa un rol desconocido: {linea.rol}"
            )


@pytest.mark.parametrize(
    "total,pesos",
    [
        ("100.00", ["1", "1", "1"]),
        ("0.01", ["1", "1"]),
        ("999.99", ["7", "13", "3"]),
        ("50.00", ["1"]),
    ],
)
def test_reparto_proporcional_conserva_el_total(total, pesos):
    partes = plantillas.reparto_proporcional(
        Decimal(total), [Decimal(p) for p in pesos]
    )
    assert sum(partes) == Decimal(total)


def test_reparto_proporcional_sin_pesos_devuelve_vacio():
    """Quien llama vuelve a la línea sin repartir, que es lo de siempre."""
    assert plantillas.reparto_proporcional(Decimal("10"), []) == []
    assert plantillas.reparto_proporcional(Decimal("10"), [Decimal(0)]) == []


def test_la_categoria_devuelve_su_configuracion(env):
    """`asiento_contable_config` era un campo de **solo escritura**: se podía
    guardar y `CategoriaOut` no lo devolvía, así que ninguna pantalla podía
    mostrarlo ni precargarlo para corregirlo."""
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)

    creada = _categoria(client, h, ids, "Lista", config={"ingreso": "7021"})
    assert creada.status_code == 201
    assert creada.json()["asiento_contable_config"] == {"ingreso": "7021"}

    hija = _categoria(client, h, ids, "Sub", padre_id=creada.json()["id"]).json()
    assert hija["padre_id"] == creada.json()["id"]

    # `{}` limpia el mapa; ausente no lo toca.
    vaciada = client.patch(
        f"/api/v1/inventory/categorias/{creada.json()['id']}", headers=h,
        json={"asiento_contable_config": {}},
    )
    assert vaciada.json()["asiento_contable_config"] == {}

    sin_tocar = client.patch(
        f"/api/v1/inventory/categorias/{hija['id']}", headers=h, json={"nombre": "Sub 2"}
    )
    assert sin_tocar.json()["nombre"] == "Sub 2"


def test_un_servicio_no_admite_sku(env):
    """Un SKU de un servicio sería una fila de stock que nada mueve, y dos
    verdades sobre si la cosa se inventaría."""
    client, ids, _ = env
    h = _token(client)
    articulo_id = _articulo(client, h, ids, "X001", tipo="servicio")

    r = client.post(
        "/api/v1/inventory/skus", headers=h,
        json={"articulo_id": articulo_id, "codigo": "SKU-SERVICIO"},
    )
    assert r.status_code == 409
    assert "no lleva SKU" in r.json()["detail"]
