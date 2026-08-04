"""Motor de sync del hub de sucursal (ADR-009, fase 2).

Monta las DOS bases —la nube y el hub— en el mismo test y sincroniza entre
ellas por la API real de la nube: el hub habla HTTP contra un `TestClient`
autenticado con su cuenta de servicio, igual que en producción. Así lo que
se prueba es el camino completo (permisos, tenant, contrato de cable,
watermark), no un motor conversando consigo mismo.
"""

import uuid
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.config.settings import settings
from src.core.app import create_app
from src.core.database import Base
from src.core.sync import estado_conexion, motor, watermark
from src.core.sync.cliente_nube import ClienteNube, ErrorNube
from src.core.sync.contratos import PULL, PUSH, RecursoSync
from src.modules.inventory.application import listeners
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    Receta,
    RecetaItem,
    Sku,
    Stock,
    UnidadMedida,
)
from src.modules.sales.application import sincronizacion as sales_sync
from src.modules.sales.application import ventas as ventas_uc
from src.modules.sales.infrastructure.models import (
    ListaPrecio,
    MedioPago,
    Pago,
    Precio,
    ProductoComercial,
    PuntoVenta,
    Venta,
    VentaItem,
)
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Grupo,
    Marca,
    Permiso,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin, verify_pin
from src.seeders.hub import alta_hub
from src.seeders.seed import seed
from src.shared import fechas

PIN_CAJERO = "123456"
PIN_HUB = "654321"


def _base():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _poblar_nube(Session) -> dict:
    """Organización + catálogo + cajero + cuenta de servicio del hub."""
    ids = {}
    with Session() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        grupo = s.scalar(select(Grupo))
        marca = s.scalar(select(Marca).where(Marca.grupo_id == grupo.id))
        sucursal = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre="Tarapoto Centro",
            direccion="Jr. X 123", tenencia="alquilada",
        )
        s.add(sucursal)
        s.flush()
        almacen = Almacen(
            empresa_id=empresa.id, sucursal_id=sucursal.id,
            nombre="Almacén Tarapoto", tipo="sucursal",
        )
        pv = PuntoVenta(
            sucursal_id=sucursal.id, canal="trabajador", serie_boleta="B001",
            serie_factura="F001", politica_pago="adelantado",
        )
        udm_cat = CategoriaUdm(nombre="Peso")
        s.add_all([almacen, pv, udm_cat])
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo")
        s.add(udm)
        s.flush()
        harina = Articulo(
            empresa_id=empresa.id, id_interno="H001", nombre="Harina",
            unidad_medida_id=udm.id, tipo="insumo",
        )
        s.add(harina)
        s.flush()
        sku = Sku(articulo_id=harina.id, codigo="SKU-HARINA")
        receta = Receta(
            nombre="Pizza base", rendimiento_cantidad=Decimal(1),
            rendimiento_unidad_medida_id=udm.id,
        )
        s.add_all([sku, receta])
        s.flush()
        s.add(RecetaItem(receta_id=receta.id, articulo_id=harina.id,
                         cantidad=Decimal("0.25")))
        producto = ProductoComercial(
            id_interno="P001", marca_id=marca.id, nombre="Pizza Clásica",
            receta_id=receta.id,
        )
        medio = MedioPago(
            empresa_id=empresa.id, nombre="Efectivo", direccion="cobro",
            tipo="efectivo",
        )
        s.add_all([producto, medio])
        s.flush()
        # El precio lo fija el servidor (RN-PRC-003): el hub necesita la
        # lista replicada para poder cotizar durante el corte.
        lista = ListaPrecio(marca_id=marca.id, nombre="Regular",
                            vigente_desde=date(2020, 1, 1))
        s.add(lista)
        s.flush()
        s.add(Precio(lista_precio_id=lista.id, producto_comercial_id=producto.id,
                     monto=Decimal("25.00")))
        s.add(Stock(almacen_id=almacen.id, sku_id=sku.id, cantidad=Decimal(10)))

        cajero = Usuario(
            username="cajero_tarapoto", pin_hash=hash_pin(PIN_CAJERO),
            tipo="humano", nombre_display="Cajero Tarapoto", activo=True,
        )
        s.add(cajero)
        s.flush()
        rol_cajero = s.scalar(select(Rol).where(Rol.nombre == "cajero"))
        s.add_all([
            UsuarioRol(usuario_id=cajero.id, rol_id=rol_cajero.id),
            UsuarioSucursal(usuario_id=cajero.id, sucursal_id=sucursal.id),
        ])
        hub = alta_hub(s, sucursal.id, "hub_tarapoto", PIN_HUB)
        ids.update(
            empresa_id=empresa.id, sucursal_id=sucursal.id, almacen_id=almacen.id,
            pv_id=pv.id, producto_id=producto.id, medio_id=medio.id, sku_id=sku.id,
            cajero_id=cajero.id, hub_usuario_id=hub.id, marca_id=marca.id,
        )
        s.commit()
    return ids


class ClienteDeTest:
    """Mismo contrato que `ClienteNube`, pero sobre el `TestClient` de la
    nube en vez de la red."""

    def __init__(self, client: TestClient, token: str) -> None:
        self.client = client
        self.headers = {"Authorization": f"Bearer {token}"}
        self.llamadas: list[tuple] = []

    def pull(self, recurso, desde, limite):
        params = {"recurso": recurso, "limite": limite}
        if desde is not None:
            params["desde"] = desde.isoformat()
        self.llamadas.append(("pull", recurso))
        r = self.client.get("/api/v1/sync/pull", params=params, headers=self.headers)
        if r.is_error:
            raise ErrorNube(f"pull {recurso} → {r.status_code}: {r.text}")
        return r.json()

    def push(self, lote):
        self.llamadas.append(("push", len(lote["ventas"]), len(lote["pagos"])))
        r = self.client.post(
            "/api/v1/sync/push", json={"sales": lote}, headers=self.headers
        )
        if r.is_error:
            raise ErrorNube(f"push → {r.status_code}: {r.text}")
        return r.json()

    def cerrar(self):
        pass


class Entorno:
    def __init__(self, NubeSession, HubSession, client, cliente, ids):
        self.NubeSession = NubeSession
        self.HubSession = HubSession
        self.client = client
        self.cliente = cliente
        self.ids = ids

    def ciclo(self):
        return motor.ciclo(session_factory=self.HubSession, cliente=self.cliente)

    @contextmanager
    def listeners_en(self, cual: str):
        """El listener de inventario es global al proceso; en producción hay
        un proceso por base. Acá se apunta a la que corresponde."""
        anterior = listeners.session_factory
        listeners.session_factory = (
            self.HubSession if cual == "hub" else self.NubeSession
        )
        try:
            yield
        finally:
            listeners.session_factory = anterior


@pytest.fixture()
def entorno(monkeypatch):
    NubeSession = _base()
    HubSession = _base()
    ids = _poblar_nube(NubeSession)

    monkeypatch.setattr(settings, "deployment_mode", "hub")
    monkeypatch.setattr(settings, "hub_empresa_id", str(ids["empresa_id"]))
    monkeypatch.setattr(settings, "hub_sucursal_id", str(ids["sucursal_id"]))
    monkeypatch.setattr(settings, "sync_lote_maximo", 100)
    monkeypatch.setattr(estado_conexion, "_pingar", lambda: True)
    monkeypatch.setattr(estado_conexion, "_estado", estado_conexion.EN_LINEA)
    monkeypatch.setattr(estado_conexion, "_fallos_consecutivos", 0)
    # El listener corre contra la nube salvo que un test diga lo contrario.
    monkeypatch.setattr(listeners, "session_factory", NubeSession)

    app = create_app()

    def _override_get_db():
        session = NubeSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        token = client.post(
            "/api/v1/auth/login",
            json={"username": "hub_tarapoto", "pin": PIN_HUB},
        ).json()["access_token"]
        yield Entorno(
            NubeSession, HubSession, client, ClienteDeTest(client, token), ids
        )


def _stock(Session, almacen_id) -> Decimal:
    with Session() as s:
        fila = s.scalar(select(Stock).where(Stock.almacen_id == almacen_id))
        return fila.cantidad if fila else None


def _venta_offline(entorno, key="venta-offline-1", cantidad="2") -> uuid.UUID:
    """Una venta cobrada en el hub durante el corte."""
    with entorno.listeners_en("hub"), entorno.HubSession() as s:
        venta = ventas_uc.crear_venta(
            s,
            sucursal_id=entorno.ids["sucursal_id"],
            punto_venta_id=entorno.ids["pv_id"],
            canal="pdv",
            modalidad="takeout",
            usuario_id=entorno.ids["cajero_id"],
            idempotency_key=key,
            items=[{
                "producto_comercial_id": entorno.ids["producto_id"],
                "cantidad": Decimal(cantidad),
                "precio_unitario": Decimal("25.00"),
            }],
            referencia_atencion="Mesa 5",
        )
        ventas_uc.registrar_pago(
            s,
            venta_id=venta.id,
            medio_pago_id=entorno.ids["medio_id"],
            monto=venta.total,
            idempotency_key=f"pago-{key}",
        )
        s.commit()
        return venta.id


# --- Descendente: nube → hub ---------------------------------------------------
def test_carga_inicial_replica_catalogo_stock_y_rbac(entorno):
    resumen = entorno.ciclo()
    assert resumen["ejecutado"] is True
    assert resumen["pull"]["errores"] == []

    with entorno.HubSession() as s:
        assert s.scalar(select(func.count()).select_from(ProductoComercial)) == 1
        assert s.scalar(select(func.count()).select_from(MedioPago)) == 1
        assert s.scalar(select(func.count()).select_from(PuntoVenta)) == 1
        assert s.scalar(select(func.count()).select_from(RecetaItem)) == 1
        # Sin lista de precios el hub no puede cotizar una venta offline.
        assert s.scalar(select(func.count()).select_from(ListaPrecio)) == 1
        assert s.scalar(select(Precio)).monto == Decimal("25.00")
        assert s.scalar(select(Stock)).cantidad == Decimal(10)
        # RBAC completo: sin esto nadie se autentica durante el corte.
        assert s.scalar(select(func.count()).select_from(Permiso)) > 0
        assert s.get(Sucursal, entorno.ids["sucursal_id"]) is not None


def test_el_cajero_puede_autenticarse_en_el_hub_sin_nube(entorno):
    """El objetivo entero del ADR: el PIN se valida contra el hash
    replicado, sin una sola llamada a la nube."""
    entorno.ciclo()
    with entorno.HubSession() as s:
        cajero = s.get(Usuario, entorno.ids["cajero_id"])
        assert cajero is not None
        assert verify_pin(cajero.pin_hash, PIN_CAJERO)


def test_el_lockout_no_se_replica(entorno):
    """`intentos_fallidos`/`bloqueado_hasta` son estado vivo de cada lado:
    replicarlos bloquearía a un cajero en el local por intentos hechos
    contra la nube."""
    entorno.ciclo()
    with entorno.HubSession() as s:
        assert s.get(Usuario, entorno.ids["cajero_id"]).intentos_fallidos == 0
    campos = next(
        r.campos for r in motor.registro.RECURSOS if r.nombre == "usuario"
    )
    assert "intentos_fallidos" not in campos
    assert "bloqueado_hasta" not in campos


def test_pull_incremental_solo_trae_lo_que_cambio(entorno):
    primero = entorno.ciclo()

    with entorno.NubeSession() as s:
        producto = s.get(ProductoComercial, entorno.ids["producto_id"])
        producto.nombre = "Pizza Clásica XL"
        s.commit()

    segundo = entorno.ciclo()
    with entorno.HubSession() as s:
        assert s.get(
            ProductoComercial, entorno.ids["producto_id"]
        ).nombre == "Pizza Clásica XL"
        assert watermark.leer(s, PULL, "producto_comercial") is not None
    assert segundo["pull"]["filas"] <= primero["pull"]["filas"]


def test_el_pull_no_vuelve_a_traer_lo_viejo(entorno):
    """El recorte incremental, sin el ruido de reloj de SQLite: con marcas
    explícitas y distintas, `desde` deja afuera lo anterior."""
    from src.core.sync import exportador, registro
    from src.core.sync.contratos import AlcanceHub

    viejo = datetime(2026, 1, 1, tzinfo=UTC)
    nuevo = datetime(2026, 6, 1, tzinfo=UTC)
    with entorno.NubeSession() as s:
        permisos = list(s.scalars(select(Permiso).order_by(Permiso.codigo)))
        for permiso in permisos:
            permiso.updated_at = viejo
        permisos[0].updated_at = nuevo  # el único tocado después
        s.commit()

        alcance = AlcanceHub(entorno.ids["empresa_id"], entorno.ids["sucursal_id"])
        recurso = registro.obtener("permiso")
        desde_nuevo = exportador.exportar(s, recurso, alcance, nuevo, 500)
        assert [f["codigo"] for f in desde_nuevo] == [permisos[0].codigo]
        assert len(exportador.exportar(s, recurso, alcance, viejo, 500)) == len(permisos)


def test_recurso_desconocido_no_se_puede_pedir(entorno):
    r = entorno.client.get(
        "/api/v1/sync/pull",
        params={"recurso": "audit_log"},
        headers=entorno.cliente.headers,
    )
    assert r.status_code == 404


def test_el_hub_solo_ve_su_sucursal(entorno):
    """Otra sucursal en la misma empresa no viaja al hub."""
    with entorno.NubeSession() as s:
        otra = Sucursal(
            marca_id=entorno.ids["marca_id"], empresa_id=entorno.ids["empresa_id"],
            nombre="Otra", direccion="Jr. Y 456", tenencia="propia",
        )
        s.add(otra)
        s.flush()
        s.add(PuntoVenta(
            sucursal_id=otra.id, canal="trabajador", serie_boleta="B002",
            serie_factura="F002", politica_pago="adelantado",
        ))
        s.commit()
        otra_id = otra.id

    entorno.ciclo()
    with entorno.HubSession() as s:
        assert s.get(Sucursal, otra_id) is None
        assert s.scalar(select(func.count()).select_from(PuntoVenta)) == 1


def test_cuenta_sin_permiso_de_sync_no_puede_jalar(entorno):
    """El `pin_hash` sale por acá: el permiso no es decorativo."""
    token = entorno.client.post(
        "/api/v1/auth/login", json={"username": "cajero_tarapoto", "pin": PIN_CAJERO}
    ).json()["access_token"]
    r = entorno.client.get(
        "/api/v1/sync/pull",
        params={"recurso": "usuario"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_cuenta_de_sync_sin_sucursal_unica_es_rechazada(entorno):
    """Un hub es de un local. Con dos sucursales asignadas, el sync sería
    una fuga entre locales — se corta antes de exportar nada."""
    with entorno.NubeSession() as s:
        otra = Sucursal(
            marca_id=entorno.ids["marca_id"], empresa_id=entorno.ids["empresa_id"],
            nombre="Otra", direccion="Jr. Y 456", tenencia="propia",
        )
        s.add(otra)
        s.flush()
        s.add(UsuarioSucursal(
            usuario_id=entorno.ids["hub_usuario_id"], sucursal_id=otra.id
        ))
        s.commit()

    r = entorno.client.get(
        "/api/v1/sync/pull",
        params={"recurso": "producto_comercial"},
        headers=entorno.cliente.headers,
    )
    assert r.status_code == 403


# --- Ascendente: hub → nube ----------------------------------------------------
def test_venta_offline_se_reproduce_en_la_nube_con_su_identidad(entorno):
    entorno.ciclo()
    venta_id = _venta_offline(entorno)

    resumen = entorno.ciclo()
    assert resumen["push"]["errores"] == []

    with entorno.NubeSession() as s:
        venta = s.get(Venta, venta_id)
        assert venta is not None, "la venta conserva su id en la nube"
        assert venta.estado == "pagada"
        assert venta.total == Decimal("50.00")
        assert venta.usuario_id == entorno.ids["cajero_id"], "no la vendió el hub"
        assert venta.referencia_atencion == "Mesa 5"
        assert venta.numero_orden == 1
        assert venta.fecha_orden == fechas.hoy()
        assert s.scalar(select(func.count()).select_from(Pago)) == 1


def test_la_nube_descuenta_su_propio_stock_al_recibir_la_venta(entorno):
    """El hub NO empuja movimientos: los genera el listener de la nube al
    recibir la venta. Empujarlos además duplicaría el consumo."""
    entorno.ciclo()
    _venta_offline(entorno)
    assert _stock(entorno.HubSession, entorno.ids["almacen_id"]) == Decimal("9.5")

    entorno.ciclo()
    assert _stock(entorno.NubeSession, entorno.ids["almacen_id"]) == Decimal("9.5")
    # Y tras el pull del mismo ciclo, ambos lados coinciden.
    assert _stock(entorno.HubSession, entorno.ids["almacen_id"]) == Decimal("9.5")


def test_reintentar_el_push_no_duplica_la_venta(entorno):
    entorno.ciclo()
    _venta_offline(entorno)
    entorno.ciclo()
    # Segundo ciclo: la marca ya avanzó, pero aunque el lote se repita la
    # idempotencia lo absorbe.
    with entorno.HubSession() as s:
        watermark.registrar_ok(s, PUSH, sales_sync.RECURSO_PUSH, None)
        fila = s.get(motor.watermark.SyncWatermark, (PUSH, sales_sync.RECURSO_PUSH))
        fila.marca = None
        s.commit()
    entorno.ciclo()

    with entorno.NubeSession() as s:
        assert s.scalar(select(func.count()).select_from(Venta)) == 1
        assert s.scalar(select(func.count()).select_from(Pago)) == 1
        assert _stock(entorno.NubeSession, entorno.ids["almacen_id"]) == Decimal("9.5")


def test_anulacion_offline_viaja_y_repone_stock_en_la_nube(entorno):
    entorno.ciclo()
    with entorno.listeners_en("hub"), entorno.HubSession() as s:
        venta = ventas_uc.crear_venta(
            s,
            sucursal_id=entorno.ids["sucursal_id"],
            punto_venta_id=entorno.ids["pv_id"],
            canal="pdv", modalidad="mesa",
            usuario_id=entorno.ids["cajero_id"],
            idempotency_key="venta-a-anular",
            items=[{
                "producto_comercial_id": entorno.ids["producto_id"],
                "cantidad": Decimal("4"),
                "precio_unitario": Decimal("25.00"),
            }],
        )
        ventas_uc.anular_venta(s, venta.id, entorno.ids["cajero_id"])
        s.commit()
        venta_id = venta.id

    resumen = entorno.ciclo()
    assert resumen["push"]["errores"] == []
    with entorno.NubeSession() as s:
        assert s.get(Venta, venta_id).estado == "anulada"
    # Consumió 1 kg y lo repuso: la nube queda como estaba.
    assert _stock(entorno.NubeSession, entorno.ids["almacen_id"]) == Decimal("10")


def test_una_venta_rechazada_no_arrastra_al_resto_ni_avanza_la_marca(entorno):
    """La nube rechaza lo que no puede aceptar (acá: un producto que no
    existe de su lado) e informa el ítem, sin tumbar el lote ni perderlo."""
    entorno.ciclo()
    _venta_offline(entorno, key="venta-buena")
    # Una venta que en el hub existe pero que la nube no puede aceptar: su
    # producto ya no está de ese lado (se descontinuó durante el corte).
    with entorno.HubSession() as s:
        fantasma = Venta(
            sucursal_id=entorno.ids["sucursal_id"],
            punto_venta_id=entorno.ids["pv_id"],
            fecha_orden=fechas.hoy(), numero_orden=99,
            canal="pdv", modalidad="mesa",
            usuario_id=entorno.ids["cajero_id"],
            estado="orden", total=Decimal("10.00"),
            idempotency_key="venta-fantasma",
        )
        s.add(fantasma)
        s.flush()
        s.add(VentaItem(
            venta_id=fantasma.id, producto_comercial_id=uuid.uuid4(),
            cantidad=Decimal("1"), precio_unitario=Decimal("10.00"),
        ))
        s.commit()

    resumen = entorno.ciclo()
    assert len(resumen["push"]["errores"]) == 1
    assert resumen["push"]["errores"][0]["tipo"] == "venta"

    with entorno.NubeSession() as s:
        assert s.scalar(select(func.count()).select_from(Venta)) == 1
    with entorno.HubSession() as s:
        # La marca NO avanzó: el lote se reintenta entero.
        assert watermark.leer(s, PUSH, sales_sync.RECURSO_PUSH) is None
        fila = s.get(motor.watermark.SyncWatermark, (PUSH, sales_sync.RECURSO_PUSH))
        assert "rechazados" in fila.ultimo_error


def test_el_hub_no_puede_empujar_ventas_de_otra_sucursal(entorno):
    entorno.ciclo()
    lote = {
        "ventas": [{
            "id": str(uuid.uuid4()),
            "sucursal_id": str(uuid.uuid4()),
            "punto_venta_id": str(entorno.ids["pv_id"]),
            "canal": "pdv", "modalidad": "mesa",
            "usuario_id": str(entorno.ids["cajero_id"]),
            "idempotency_key": "venta-ajena",
            "fecha_orden": fechas.hoy().isoformat(),
            "numero_orden": 1,
            "estado": "orden",
            "items": [{
                "producto_comercial_id": str(entorno.ids["producto_id"]),
                "cantidad": "1", "precio_unitario": "10.00", "descuento": "0",
            }],
        }],
        "pagos": [],
    }
    respuesta = entorno.cliente.push(lote)
    assert respuesta["ventas"] == 0
    assert respuesta["errores"][0]["detalle"] == "fuera de la sucursal del hub"


# --- Ciclo, estado y fallas -----------------------------------------------------
def test_offline_no_intenta_sincronizar(entorno, monkeypatch):
    monkeypatch.setattr(estado_conexion, "_pingar", lambda: False)
    monkeypatch.setattr(estado_conexion, "_estado", estado_conexion.OFFLINE)
    resumen = entorno.ciclo()
    assert resumen == {
        "ejecutado": False,
        "motivo": "offline",
        "conexion": estado_conexion.estado_actual(),
    }
    assert entorno.cliente.llamadas == []


def test_en_modo_cloud_el_ciclo_no_hace_nada(entorno, monkeypatch):
    monkeypatch.setattr(settings, "deployment_mode", "cloud")
    assert entorno.ciclo() == {"ejecutado": False, "motivo": "deployment_mode=cloud"}


def test_un_recurso_que_falla_no_cancela_los_demas(entorno, monkeypatch):
    pull_real = entorno.cliente.pull

    def _pull(recurso, desde, limite):
        if recurso == "stock":
            raise ErrorNube("la nube cortó a mitad del stock")
        return pull_real(recurso, desde, limite)

    monkeypatch.setattr(entorno.cliente, "pull", _pull)
    resumen = entorno.ciclo()

    assert [e["recurso"] for e in resumen["pull"]["errores"]] == ["stock"]
    with entorno.HubSession() as s:
        assert s.scalar(select(func.count()).select_from(ProductoComercial)) == 1
        assert s.scalar(select(func.count()).select_from(Stock)) == 0
        assert watermark.leer(s, PULL, "stock") is None
        fila = s.get(motor.watermark.SyncWatermark, (PULL, "stock"))
        assert "cortó" in fila.ultimo_error


def test_health_sync_muestra_el_avance_por_recurso(entorno, monkeypatch):
    entorno.ciclo()
    # `/health/sync` corre en el proceso de la API y lee la base del hub.
    monkeypatch.setattr(
        "src.core.health_router.SessionLocal", entorno.HubSession
    )
    cuerpo = entorno.client.get("/health/sync").json()
    assert cuerpo["aplica"] is True
    recursos = {(r["direccion"], r["recurso"]): r for r in cuerpo["recursos"]}
    assert recursos[(PULL, "producto_comercial")]["ultimo_ok"] is not None
    assert recursos[(PULL, "producto_comercial")]["ultimo_error"] is None


def test_el_hub_no_encola_comprobantes(entorno, monkeypatch):
    """Sin Celery ni Redis en el Raspberry Pi: cobrar offline no puede
    intentar hablarle a un broker que no existe (ADR-009)."""
    from src.modules.sales.application import tasks

    llamadas = []
    monkeypatch.setattr(
        tasks.emitir_comprobante, "delay", lambda cid: llamadas.append(cid)
    )
    monkeypatch.setattr(settings, "factiliza_token", "token-de-prueba")
    tasks.encolar(uuid.uuid4())
    assert llamadas == [], "un hub nunca emite a SUNAT"

    monkeypatch.setattr(settings, "deployment_mode", "cloud")
    tasks.encolar(uuid.uuid4())
    assert len(llamadas) == 1, "la nube sí encola"


# --- Alta de la cuenta de servicio ----------------------------------------------
def test_alta_de_hub_es_idempotente(entorno):
    with entorno.NubeSession() as s:
        antes = alta_hub(s, entorno.ids["sucursal_id"], "hub_tarapoto", PIN_HUB)
        s.commit()
        assert antes.id == entorno.ids["hub_usuario_id"]
        assert s.scalar(
            select(func.count()).select_from(UsuarioSucursal).where(
                UsuarioSucursal.usuario_id == antes.id
            )
        ) == 1


def test_reasignar_un_hub_deja_una_sola_sucursal(entorno):
    """Mover un hub de local no puede dejarlo viendo los dos: la API de
    sync rechazaría la cuenta y el hub quedaría mudo."""
    with entorno.NubeSession() as s:
        otra = Sucursal(
            marca_id=entorno.ids["marca_id"], empresa_id=entorno.ids["empresa_id"],
            nombre="Otra", direccion="Jr. Y 456", tenencia="propia",
        )
        s.add(otra)
        s.flush()
        usuario = alta_hub(s, otra.id, "hub_tarapoto", PIN_HUB)
        s.commit()
        asignadas = list(s.scalars(
            select(UsuarioSucursal.sucursal_id).where(
                UsuarioSucursal.usuario_id == usuario.id
            )
        ))
        assert asignadas == [otra.id]


# --- Contrato y cliente HTTP ----------------------------------------------------
def test_recurso_con_campo_inexistente_no_se_declara():
    """El descriptor se valida al importarse: un campo mal escrito rompe el
    arranque, no un ciclo de sync a las tres de la mañana."""
    with pytest.raises(ValueError, match="campos inexistentes"):
        RecursoSync(
            nombre="roto", modelo=Venta, campos=("id", "no_existe"),
            filtro=lambda q, a: q,
        )


def test_recurso_sin_pk_en_campos_no_se_declara():
    with pytest.raises(ValueError, match="debe viajar en campos"):
        RecursoSync(
            nombre="sin_pk", modelo=Venta, campos=("total", "updated_at"),
            filtro=lambda q, a: q,
        )


def test_endpoint_de_recursos_documenta_el_contrato(entorno):
    filas = entorno.client.get(
        "/api/v1/sync/recursos", headers=entorno.cliente.headers
    ).json()
    nombres = [f["nombre"] for f in filas]
    assert "producto_comercial" in nombres
    assert all(f["motivo"] for f in filas), "cada recurso explica por qué viaja"


def test_el_cliente_reintenta_una_vez_tras_401():
    """El access token dura minutos y el hub sincroniza por horas: que
    expire es lo normal, no un error."""
    peticiones = []

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/login"):
            peticiones.append("login")
            return httpx.Response(200, json={"access_token": "t", "token_type": "bearer"})
        peticiones.append("pull")
        if peticiones.count("pull") == 1:
            return httpx.Response(401, json={"detail": "expirado"})
        return httpx.Response(200, json={"recurso": "rol", "filas": [], "hay_mas": False})

    cliente = ClienteNube(
        base_url="https://nube.local",
        username="hub",
        pin="654321",
        cliente_http=httpx.Client(transport=httpx.MockTransport(_handler)),
    )
    assert cliente.pull("rol", None, 10)["filas"] == []
    assert peticiones == ["login", "pull", "login", "pull"]


def test_el_cliente_convierte_una_caida_de_red_en_error_de_sync():
    def _handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin ruta")

    cliente = ClienteNube(
        base_url="https://nube.local", username="hub", pin="654321",
        cliente_http=httpx.Client(transport=httpx.MockTransport(_handler)),
    )
    with pytest.raises(ErrorNube):
        cliente.pull("rol", None, 10)
