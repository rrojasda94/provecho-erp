"""Tests del slice de cupón de promoción (ADR-059): la landing pública del
QR emite, la caja canjea.

Mismo patrón que `test_sales.py` — SQLite en memoria, seeder real (para que
la promoción semilla y los permisos existan) y override de `get_db`.

Lo que se prueba con más insistencia es el «un solo uso»: es la única
promesa de la campaña que, si falla, regala dinero.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.app import create_app
from src.core.database import Base
from src.modules.accounting.application import listeners as accounting_listeners
from src.modules.inventory.application import listeners as inventory_listeners
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    Receta,
    RecetaItem,
    Sku,
    Stock,
    UnidadMedida,
)
from src.modules.marketing.application import listeners as marketing_listeners
from src.modules.reports.application import listeners as reports_listeners
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import (
    Cliente,
    Cupon,
    ListaPrecio,
    MedioPago,
    Precio,
    ProductoComercial,
    PromocionCupon,
    PuntoVenta,
)
from src.modules.users.api.deps import get_db, get_db_reportes
from src.modules.users.application import listeners as users_listeners
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Grupo,
    Marca,
    Persona,
    Sucursal,
    Usuario,
    UsuarioSucursal,
)
from src.shared import fechas
from tests.conftest import abrir_caja_directa

PUBLICO = "/api/v1/sales/publico/reconocerte"
DNI = "70123456"
TELEFONO = "987654321"


@pytest.fixture()
def env(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    # Los listeners que despierta este test: el registro publica
    # `sales.cliente_registrado_en_promocion` (marketing) y crear una venta
    # despierta a los otros cuatro. Sin esto irían a la base de producción y
    # el guardián de `conftest` los cortaría — se lo tragan y lo loguean,
    # así que el test pasaría igual sin ejercitar nada.
    for modulo in (
        marketing_listeners,
        accounting_listeners,
        inventory_listeners,
        reports_listeners,
        users_listeners,
    ):
        monkeypatch.setattr(modulo, "session_factory", TestSession)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        grupo = s.scalar(select(Grupo))
        marca = s.scalar(select(Marca).where(Marca.grupo_id == grupo.id))
        sucursal = Sucursal(
            marca_id=marca.id,
            empresa_id=empresa.id,
            nombre="Tarapoto Centro",
            direccion="Jr. X 123",
            tenencia="alquilada",
        )
        s.add(sucursal)
        s.flush()
        almacen = Almacen(
            empresa_id=empresa.id,
            sucursal_id=sucursal.id,
            nombre="Almacén Tarapoto",
            tipo="sucursal",
        )
        pv = PuntoVenta(
            sucursal_id=sucursal.id,
            canal="trabajador",
            serie_boleta="B001",
            serie_factura="F001",
            politica_pago="adelantado",
        )
        udm_cat = CategoriaUdm(nombre="Peso")
        s.add_all([almacen, pv, udm_cat])
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo")
        s.add(udm)
        s.flush()
        harina = Articulo(
            empresa_id=empresa.id,
            id_interno="H001",
            nombre="Harina",
            unidad_medida_id=udm.id,
            tipo="insumo",
        )
        s.add(harina)
        s.flush()
        sku = Sku(articulo_id=harina.id, codigo="SKU-HARINA")
        receta = Receta(
            empresa_id=empresa.id,
            nombre="Pizza base",
            rendimiento_cantidad=Decimal(1),
            rendimiento_unidad_medida_id=udm.id,
        )
        s.add_all([sku, receta])
        s.flush()
        s.add(
            RecetaItem(receta_id=receta.id, articulo_id=harina.id, cantidad=Decimal("0.1"))
        )
        producto = ProductoComercial(
            id_interno="P001",
            marca_id=marca.id,
            nombre="Pizza Clásica",
            receta_id=receta.id,
        )
        medio = MedioPago(
            empresa_id=empresa.id, nombre="Efectivo", direccion="cobro", tipo="efectivo"
        )
        s.add_all([producto, medio])
        s.flush()
        lista = ListaPrecio(
            marca_id=marca.id, nombre="Regular", vigente_desde=date(2020, 1, 1)
        )
        s.add(lista)
        s.flush()
        s.add(
            Precio(
                lista_precio_id=lista.id,
                producto_comercial_id=producto.id,
                monto=Decimal("50.00"),
            )
        )
        s.add(Stock(almacen_id=almacen.id, sku_id=sku.id, cantidad=Decimal(100)))
        admin = s.scalar(select(Usuario).where(Usuario.username == "admin"))
        # El seeder asignó los usuarios a las sucursales que existían
        # entonces; esta es posterior, y sin la asignación el JWT sale sin
        # alcance sobre ella y toda la caja responde 403 (ADR-004).
        for usuario in s.scalars(select(Usuario)):
            s.add(UsuarioSucursal(usuario_id=usuario.id, sucursal_id=sucursal.id))
        s.flush()
        abrir_caja_directa(s, punto_venta_id=pv.id, cajero_id=admin.id)
        promocion = s.scalar(select(PromocionCupon))
        ids.update(
            sucursal_id=str(sucursal.id),
            pv_id=str(pv.id),
            producto_id=str(producto.id),
            grupo_id=str(grupo.id),
            promocion_id=str(promocion.id),
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
    app.dependency_overrides[get_db_reportes] = _override_get_db
    with TestClient(app) as c:
        yield c, ids, TestSession


def _token(client, username="admin"):
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": "123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _registro(**cambios):
    cuerpo = {
        "numero_documento": DNI,
        "nombre": "Ana Torres",
        "telefono": TELEFONO,
        "fecha_nacimiento": "1994-03-15",
        "direccion": "Jr. Lima 100",
        "acepta_terminos": True,
    }
    cuerpo.update(cambios)
    return cuerpo


def _cliente_de(TestSession, dni=DNI):
    with TestSession() as s:
        persona = s.scalar(select(Persona).where(Persona.numero_documento == dni))
        if persona is None:
            return None
        return s.scalar(select(Cliente).where(Cliente.persona_id == persona.id))


def _venta_con_cliente(client, headers, ids, cliente_id, key="cupon-venta-0001"):
    r = client.post(
        "/api/v1/sales/ventas",
        headers=headers,
        json={
            "sucursal_id": ids["sucursal_id"],
            "punto_venta_id": ids["pv_id"],
            "canal": "pdv",
            "modalidad": "takeout",
            "idempotency_key": key,
            "cliente_id": str(cliente_id),
            "items": [{"producto_comercial_id": ids["producto_id"], "cantidad": "2"}],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


# --- Reglas puras ------------------------------------------------------------
def test_vencimiento_cuenta_el_ultimo_dia_entero():
    assert rules.vencimiento_cupon(date(2026, 8, 24), 30) == date(2026, 9, 22)
    # Una vigencia de un día vale hoy, no vence ayer.
    assert rules.vencimiento_cupon(date(2026, 8, 24), 1) == date(2026, 8, 24)


def test_cupon_vigente_solo_activo_y_dentro_de_fecha():
    assert rules.cupon_vigente("activo", date(2026, 9, 22), date(2026, 9, 22))
    assert not rules.cupon_vigente("activo", date(2026, 9, 22), date(2026, 9, 23))
    assert not rules.cupon_vigente("canjeado", date(2026, 9, 22), date(2026, 9, 1))


def test_promocion_terminada_no_emite():
    assert rules.promocion_emite("activa", date(2026, 12, 31), date(2026, 8, 24))
    assert not rules.promocion_emite("terminada", date(2026, 12, 31), date(2026, 8, 24))
    assert not rules.promocion_emite("activa", date(2026, 8, 23), date(2026, 8, 24))


def test_cupon_es_motivo_de_descuento_propio():
    """Separado de `promocion` a propósito: el reporte tiene que poder decir
    qué margen se regaló a criterio y qué se había prometido en campaña."""
    assert rules.MOTIVO_CUPON in rules.MOTIVOS_DESCUENTO
    assert rules.MOTIVO_CUPON != "promocion"


# --- Landing pública ---------------------------------------------------------
def test_registro_nuevo_crea_cliente_y_entrega_cupon(env):
    client, ids, TestSession = env
    r = client.post(f"{PUBLICO}/registro", json=_registro())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["codigo"] == DNI
    assert body["ya_estaba_registrado"] is False
    assert Decimal(body["descuento_porcentaje"]) == Decimal("10")

    cliente = _cliente_de(TestSession)
    assert cliente is not None
    with TestSession() as s:
        persona = s.get(Persona, cliente.persona_id)
        assert persona.telefono == TELEFONO
        assert persona.fecha_nacimiento == date(1994, 3, 15)
        assert persona.domicilio == "Jr. Lima 100"


def test_el_cupon_vale_un_mes(env):
    client, ids, TestSession = env
    body = client.post(f"{PUBLICO}/registro", json=_registro()).json()
    with TestSession() as s:
        cupon = s.scalar(select(Cupon))
        assert date.fromisoformat(body["vigente_hasta"]) == cupon.vigente_hasta
    # Contra el día de negocio (America/Lima) y no contra `created_at`, que
    # está en UTC: de madrugada las dos fechas no son la misma y el cupón
    # aparentaría durar un día menos.
    assert cupon.vigente_hasta - fechas.hoy() == timedelta(days=29)


def test_segundo_registro_devuelve_el_mismo_cupon(env):
    """No emite un segundo: el cliente que vuelve a escanear el QR tiene que
    reencontrar SU código, no llevarse otro."""
    client, ids, TestSession = env
    primero = client.post(f"{PUBLICO}/registro", json=_registro()).json()
    segundo = client.post(f"{PUBLICO}/registro", json=_registro())
    assert segundo.status_code == 201
    assert segundo.json()["codigo"] == primero["codigo"]
    assert segundo.json()["ya_estaba_registrado"] is True
    with TestSession() as s:
        assert len(list(s.scalars(select(Cupon)))) == 1


def test_cliente_ya_registrado_por_telefono_no_se_duplica(env):
    """El caso de media base: en caja se da de alta con solo teléfono
    (RN-PTS-002). Sin este camino, esa gente entraría de nuevo como cliente
    nuevo y quedaría duplicada contra su propia ficha."""
    client, ids, TestSession = env
    h = _token(client)
    r = client.post(
        "/api/v1/sales/clientes",
        headers=h,
        json={"nombre": "Ana Torres", "telefono": TELEFONO},
    )
    assert r.status_code == 201, r.text

    r = client.post(f"{PUBLICO}/registro", json=_registro())
    assert r.status_code == 201
    assert r.json()["ya_estaba_registrado"] is True
    with TestSession() as s:
        assert len(list(s.scalars(select(Cliente)))) == 1
        # Y de paso le quedó el documento que antes no tenía.
        persona = s.scalar(select(Persona).where(Persona.telefono == TELEFONO))
        assert persona.numero_documento == DNI


def test_al_cliente_ya_registrado_se_le_completa_lo_que_faltaba(env):
    """Media base está cargada con solo teléfono o solo documento (RN-PTS-002),
    y esta es la única vez que esa gente entrega el resto. Completar lo que
    falta es la mitad del valor de la campaña — pisar lo que ya había, no:
    los datos de caja los tecleó alguien mirando al cliente."""
    client, ids, TestSession = env
    h = _token(client)
    r = client.post(
        "/api/v1/sales/clientes",
        headers=h,
        json={
            "nombre": "Ana Torres",
            "telefono": "999111222",
            "numero_documento": DNI,
        },
    )
    assert r.status_code == 201, r.text

    r = client.post(f"{PUBLICO}/registro", json=_registro())
    assert r.status_code == 201
    assert r.json()["ya_estaba_registrado"] is True
    with TestSession() as s:
        persona = s.scalar(select(Persona).where(Persona.numero_documento == DNI))
        # El teléfono de caja NO se pisa...
        assert persona.telefono == "999111222"
        # ...y lo que faltaba sí se completa.
        assert persona.fecha_nacimiento == date(1994, 3, 15)
        assert persona.domicilio == "Jr. Lima 100"


def test_el_telefono_de_alguien_ya_identificado_no_reescribe_su_dni(env):
    """Sin este candado, saber un teléfono ajeno alcanzaba para cambiarle el
    DNI a su dueño desde una página abierta a internet —y quedarse con su
    historial de compras—. El teléfono solo completa una ficha a medias; a
    una que ya tiene documento no la toca."""
    client, ids, TestSession = env
    # Ana ya está registrada, con DNI y teléfono.
    assert client.post(f"{PUBLICO}/registro", json=_registro()).status_code == 201

    # Alguien se registra con OTRO DNI y el teléfono de Ana.
    r = client.post(
        f"{PUBLICO}/registro",
        json=_registro(numero_documento="70999888", nombre="Otra Persona"),
    )
    assert r.status_code == 201
    assert r.json()["codigo"] == "70999888"
    assert r.json()["ya_estaba_registrado"] is False

    with TestSession() as s:
        ana = s.scalar(select(Persona).where(Persona.numero_documento == DNI))
        # El DNI de Ana sigue siendo el de Ana.
        assert ana is not None
        # Y el otro quedó como ficha aparte, no encima de la suya.
        otra = s.scalar(select(Persona).where(Persona.numero_documento == "70999888"))
        assert otra is not None and otra.id != ana.id
        assert len(list(s.scalars(select(Cupon)))) == 2


def test_la_consulta_publica_solo_devuelve_un_booleano(env):
    client, ids, _ = env
    r = client.post(f"{PUBLICO}/consulta", json={"numero_documento": DNI})
    assert r.status_code == 200
    assert r.json() == {"registrado": False}

    client.post(f"{PUBLICO}/registro", json=_registro())
    r = client.post(f"{PUBLICO}/consulta", json={"numero_documento": DNI})
    # Ni nombre, ni teléfono, ni cupón: la respuesta entera es el booleano.
    assert r.json() == {"registrado": True}
    r = client.post(f"{PUBLICO}/consulta", json={"telefono": TELEFONO})
    assert r.json() == {"registrado": True}


def test_la_superficie_publica_no_tiene_por_donde_borrar(env):
    """La landing escribe pero no borra: la baja de datos es un derecho ARCO
    y se atiende por el correo de los términos (ADR-011), nunca desde una
    página abierta a internet."""
    client, _, _ = env
    rutas = client.app.openapi()["paths"]
    publicas = {
        ruta: ops
        for ruta, ops in rutas.items()
        if ruta.startswith("/api/v1/sales/publico")
    }
    assert publicas
    assert all("delete" not in ops for ops in publicas.values())


def test_registro_sin_aceptar_terminos_no_entra(env):
    """El consentimiento es lo que habilita el uso comercial del dato
    (Ley 29733). Sin él, la promoción no tendría con qué sostenerlo."""
    client, _, TestSession = env
    r = client.post(f"{PUBLICO}/registro", json=_registro(acepta_terminos=False))
    assert r.status_code == 422
    with TestSession() as s:
        assert s.scalar(select(Cupon)) is None


def test_dni_invalido_no_crea_nada(env):
    client, _, TestSession = env
    r = client.post(f"{PUBLICO}/registro", json=_registro(numero_documento="123"))
    assert r.status_code == 422
    with TestSession() as s:
        assert s.scalar(select(Cliente)) is None


def test_promocion_terminada_deja_de_emitir(env):
    client, ids, TestSession = env
    h = _token(client)
    r = client.post(
        f"/api/v1/sales/promociones-cupon/{ids['promocion_id']}/termino", headers=h
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "terminada"

    r = client.post(f"{PUBLICO}/registro", json=_registro())
    assert r.status_code == 409
    r = client.get(f"{PUBLICO}/promocion")
    assert r.status_code == 409


def test_terminar_dos_veces_es_conflicto(env):
    client, ids, _ = env
    h = _token(client)
    ruta = f"/api/v1/sales/promociones-cupon/{ids['promocion_id']}/termino"
    assert client.post(ruta, headers=h).status_code == 200
    assert client.post(ruta, headers=h).status_code == 409


def test_terminar_exige_su_propio_permiso(env):
    """El cajero canjea cupones todo el día y no por eso puede apagar la
    campaña de todo el padrón."""
    client, ids, _ = env
    h = _token(client, username="cajero1")
    r = client.post(
        f"/api/v1/sales/promociones-cupon/{ids['promocion_id']}/termino", headers=h
    )
    assert r.status_code == 403


def test_la_promocion_publica_no_filtra_lo_interno(env):
    client, _, _ = env
    r = client.get(f"{PUBLICO}/promocion")
    assert r.status_code == 200
    assert set(r.json()) == {
        "nombre",
        "descuento_porcentaje",
        "vigente_hasta",
        "vigencia_cupon_dias",
    }


# --- Canje en caja -----------------------------------------------------------
def test_canje_aplica_el_diez_por_ciento_y_apaga_el_cupon(env):
    client, ids, TestSession = env
    client.post(f"{PUBLICO}/registro", json=_registro())
    cliente = _cliente_de(TestSession)
    h = _token(client)
    venta = _venta_con_cliente(client, h, ids, cliente.id)
    assert Decimal(venta["total"]) == Decimal("100.00")

    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/cupon", headers=h, json={"codigo": DNI}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert Decimal(body["monto_descuento"]) == Decimal("10.00")
    assert Decimal(body["venta"]["total"]) == Decimal("90.00")

    with TestSession() as s:
        cupon = s.scalar(select(Cupon))
        assert cupon.estado == "canjeado"
        assert str(cupon.venta_id) == venta["id"]
        assert cupon.canjeado_at is not None


def test_el_canje_no_pide_pin_de_supervisor(env):
    """A diferencia del descuento manual (RN-COM-017): ahí el margen se
    regala a criterio de alguien; acá ya estaba prometido y el cupón ES la
    autorización. El cajero lo canjea solo."""
    client, ids, TestSession = env
    client.post(f"{PUBLICO}/registro", json=_registro())
    cliente = _cliente_de(TestSession)
    h = _token(client, username="cajero1")
    venta = _venta_con_cliente(client, h, ids, cliente.id)
    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/cupon", headers=h, json={"codigo": DNI}
    )
    assert r.status_code == 200, r.text


def test_el_cupon_se_canjea_una_sola_vez(env):
    """La promesa que, si falla, regala dinero."""
    client, ids, TestSession = env
    client.post(f"{PUBLICO}/registro", json=_registro())
    cliente = _cliente_de(TestSession)
    h = _token(client)
    primera = _venta_con_cliente(client, h, ids, cliente.id, key="cupon-venta-0001")
    assert (
        client.post(
            f"/api/v1/sales/ventas/{primera['id']}/cupon", headers=h, json={"codigo": DNI}
        ).status_code
        == 200
    )
    segunda = _venta_con_cliente(client, h, ids, cliente.id, key="cupon-venta-0002")
    r = client.post(
        f"/api/v1/sales/ventas/{segunda['id']}/cupon", headers=h, json={"codigo": DNI}
    )
    assert r.status_code == 409
    # Y la segunda venta quedó intacta, sin descuento a medio aplicar.
    r = client.get(f"/api/v1/sales/ventas/{segunda['id']}", headers=h)
    assert Decimal(r.json()["total"]) == Decimal("100.00")


def test_un_cupon_canjeado_no_se_reemite(env):
    client, ids, TestSession = env
    client.post(f"{PUBLICO}/registro", json=_registro())
    cliente = _cliente_de(TestSession)
    h = _token(client)
    venta = _venta_con_cliente(client, h, ids, cliente.id)
    client.post(
        f"/api/v1/sales/ventas/{venta['id']}/cupon", headers=h, json={"codigo": DNI}
    )
    r = client.post(f"{PUBLICO}/registro", json=_registro())
    assert r.status_code == 409
    assert "usado" in r.json()["detail"]


def test_cupon_vencido_no_se_canjea(env):
    client, ids, TestSession = env
    client.post(f"{PUBLICO}/registro", json=_registro())
    cliente = _cliente_de(TestSession)
    with TestSession() as s:
        cupon = s.scalar(select(Cupon))
        cupon.vigente_hasta = date(2020, 1, 1)
        s.commit()
    h = _token(client)
    venta = _venta_con_cliente(client, h, ids, cliente.id)
    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/cupon", headers=h, json={"codigo": DNI}
    )
    assert r.status_code == 409
    assert "venció" in r.json()["detail"]


def test_el_cupon_es_nominal(env):
    """El código es el DNI, así que quien conozca uno ajeno podría
    intentarlo. Atarlo al cliente de la venta es lo que acota ese costo
    (ADR-059)."""
    client, ids, TestSession = env
    client.post(f"{PUBLICO}/registro", json=_registro())
    client.post(
        f"{PUBLICO}/registro",
        json=_registro(
            numero_documento="70999888",
            telefono="987000111",
            nombre="Otro Cliente",
        ),
    )
    otro = _cliente_de(TestSession, dni="70999888")
    h = _token(client)
    venta = _venta_con_cliente(client, h, ids, otro.id)
    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/cupon", headers=h, json={"codigo": DNI}
    )
    assert r.status_code == 409
    assert "otro cliente" in r.json()["detail"]


def test_venta_sin_cliente_no_admite_cupon(env):
    client, ids, _ = env
    client.post(f"{PUBLICO}/registro", json=_registro())
    h = _token(client)
    r = client.post(
        "/api/v1/sales/ventas",
        headers=h,
        json={
            "sucursal_id": ids["sucursal_id"],
            "punto_venta_id": ids["pv_id"],
            "canal": "pdv",
            "modalidad": "takeout",
            "idempotency_key": "cupon-anonima-01",
            "items": [{"producto_comercial_id": ids["producto_id"], "cantidad": "1"}],
        },
    )
    venta = r.json()
    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/cupon", headers=h, json={"codigo": DNI}
    )
    assert r.status_code == 409
    assert "identifícalo" in r.json()["detail"]


def test_codigo_inexistente_es_404(env):
    client, ids, TestSession = env
    client.post(f"{PUBLICO}/registro", json=_registro())
    cliente = _cliente_de(TestSession)
    h = _token(client)
    venta = _venta_con_cliente(client, h, ids, cliente.id)
    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/cupon",
        headers=h,
        json={"codigo": "00000001"},
    )
    assert r.status_code == 404


def test_el_cupon_no_se_encima_a_un_descuento_manual(env):
    """`venta.descuento_*` es una fila, no una lista: aplicar los dos
    borraría uno sin que nadie se entere."""
    client, ids, TestSession = env
    client.post(f"{PUBLICO}/registro", json=_registro())
    cliente = _cliente_de(TestSession)
    h = _token(client)
    venta = _venta_con_cliente(client, h, ids, cliente.id)
    r = client.post(
        "/api/v1/auth/autorizar",
        headers=h,
        json={
            "username": "admin",
            "pin": "123456",
            "permiso": "sales.aplicar_descuento",
        },
    )
    assert r.status_code == 200, r.text
    autorizacion = r.json()["autorizacion"]
    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/descuento",
        headers=h,
        json={
            "modo": "monto",
            "valor": "5.00",
            "motivo": "cortesia",
            "autorizacion": autorizacion,
        },
    )
    assert r.status_code == 200, r.text
    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/cupon", headers=h, json={"codigo": DNI}
    )
    assert r.status_code == 409
    with TestSession() as s:
        assert s.scalar(select(Cupon)).estado == "activo"


def test_el_canje_queda_auditado(env):
    client, ids, TestSession = env
    client.post(f"{PUBLICO}/registro", json=_registro())
    cliente = _cliente_de(TestSession)
    h = _token(client)
    venta = _venta_con_cliente(client, h, ids, cliente.id)
    client.post(
        f"/api/v1/sales/ventas/{venta['id']}/cupon", headers=h, json={"codigo": DNI}
    )
    from src.shared.models import AuditLog

    with TestSession() as s:
        registros = [
            a for a in s.scalars(select(AuditLog)) if a.entidad == "cupon"
        ]
    assert len(registros) == 1
    assert registros[0].accion == "canjear"
    assert registros[0].datos_despues["codigo"] == DNI


def test_el_rate_limit_del_registro_corta(env, monkeypatch):
    """Es la única defensa de un endpoint que escribe en el padrón sin
    autenticar a nadie."""
    from src.core import rate_limit

    client, _, _ = env
    llamadas = {"n": 0}

    def _contar(nombre, sujeto, intentos, ventana):
        if nombre != "reconocerte_registro":
            return
        llamadas["n"] += 1
        if llamadas["n"] > intentos:
            from fastapi import HTTPException, status

            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "demasiados intentos")

    monkeypatch.setattr(rate_limit, "consumir", _contar)
    codigos = []
    for i in range(12):
        r = client.post(
            f"{PUBLICO}/registro",
            json=_registro(numero_documento=f"7010{i:04d}", telefono=f"98700{i:04d}"),
        )
        codigos.append(r.status_code)
    assert 429 in codigos


# --- Lo que ve marketing -----------------------------------------------------
def test_el_registro_deja_un_lead_en_la_campana(env):
    """Marketing mide la campaña por leads, y el registro del QR es uno.

    Se empareja por nombre porque `marketing` no puede leer
    `promocion_cupon` — es una tabla de `sales`.
    """
    from src.modules.marketing.infrastructure.models import Campana, Lead

    client, ids, TestSession = env
    with TestSession() as s:
        marca = s.scalar(select(Marca))
        empresa = s.scalar(select(Empresa))
        admin = s.scalar(select(Usuario).where(Usuario.username == "admin"))
        s.add(
            Campana(
                empresa_id=empresa.id,
                marca_id=marca.id,
                nombre="Queremos RE-conocerte",
                tipo="impulso_venta",
                canal="qr",
                estado="en_curso",
                creado_por=admin.id,
                idempotency_key="campana-reconocerte-0001",
            )
        )
        s.commit()

    assert client.post(f"{PUBLICO}/registro", json=_registro()).status_code == 201
    with TestSession() as s:
        leads = list(s.scalars(select(Lead)))
    assert len(leads) == 1
    assert leads[0].tipo == "registro"
    assert leads[0].canal == "qr"


def test_sin_campana_en_curso_el_registro_igual_entrega_el_cupon(env):
    """El lead es cómo Marketing mide, no parte de lo que se le prometió al
    cliente: frenar el registro porque nadie abrió el brief lo dejaría sin
    su cupón por un trámite interno."""
    from src.modules.marketing.infrastructure.models import Lead

    client, _, TestSession = env
    r = client.post(f"{PUBLICO}/registro", json=_registro())
    assert r.status_code == 201
    assert r.json()["codigo"] == DNI
    with TestSession() as s:
        assert list(s.scalars(select(Lead))) == []
