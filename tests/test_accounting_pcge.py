"""Tests del PCGE y de los estados financieros: integridad del catálogo,
cobertura del mapa rubro→línea, asientos oficiales generados por plantilla
(con y sin IGV) y cuadre del Estado de Situación Financiera y del Estado de
Resultados. SQLite en memoria + override de get_db, mismo patrón que
test_accounting.py.
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
from src.modules.accounting.application import listeners as accounting_listeners
from src.modules.accounting.domain import estados_financieros as ef
from src.modules.accounting.domain import pcge, plantillas
from src.modules.inventory.application import listeners as inventory_listeners
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Almacen, Empresa, Marca, Sucursal
from src.shared import fechas, tributos
from src.shared.models import Comprobante


# --- El catálogo, sin base de datos de por medio ------------------------------
def test_catalogo_sin_codigos_repetidos():
    codigos = [codigo for codigo, _ in pcge.CUENTAS]
    assert len(codigos) == len(set(codigos))


def test_cada_cuenta_tiene_tipo_y_padre_dentro_del_catalogo():
    """Un padre que no está en el catálogo dejaría la cuenta colgando de un
    id nulo y el árbol del plan de cuentas mostraría una divisionaria como si
    fuera un rubro."""
    for codigo, _nombre in pcge.CUENTAS:
        assert pcge.tipo_de(codigo) in (
            "activo", "pasivo", "patrimonio", "ingreso", "gasto"
        )
        padre = pcge.padre_de(codigo)
        assert padre is None or padre in pcge.DENOMINACIONES
        if len(codigo) == 2:
            assert padre is None


def test_el_padre_aparece_antes_que_sus_divisionarias():
    """`importar_pcge` arma el árbol en una sola pasada: si una divisionaria
    llegara antes que su rubro, se guardaría sin padre."""
    vistos: set[str] = set()
    for codigo, _nombre in pcge.CUENTAS:
        padre = pcge.padre_de(codigo)
        assert padre is None or padre in vistos
        vistos.add(codigo)


#: Cuentas de último nivel: las únicas que pueden recibir un asiento y, por
#: tanto, las únicas que un estado financiero tiene que saber clasificar. Un
#: rubro que agrupa nunca tiene saldo propio.
IMPUTABLES = tuple(
    codigo
    for codigo, _ in pcge.CUENTAS
    if codigo not in {pcge.padre_de(otro) for otro, _ in pcge.CUENTAS}
)


def test_toda_cuenta_de_balance_cae_en_una_linea_del_esf():
    """Una cuenta que ninguna línea reclama es un descuadre garantizado: su
    saldo existe en el mayor y no aparece en el balance."""
    huerfanas = [
        codigo
        for codigo in IMPUTABLES
        if codigo[0] in "12345" and ef.linea_de(codigo, ef.ESF) is None
    ]
    assert huerfanas == []


def test_toda_cuenta_de_resultado_cae_en_una_linea_del_er():
    secciones = tuple(
        seccion for _c, _e, secciones in ef.BLOQUES_ER for seccion in secciones
    )
    huerfanas = [
        codigo
        for codigo in IMPUTABLES
        if codigo[0] in "6789"
        and not ef.es_reclasificacion(codigo)
        and ef.linea_de(codigo, secciones) is None
    ]
    assert huerfanas == []


def test_la_reclasificacion_por_funcion_queda_fuera_del_estado_por_naturaleza():
    """La 79 y el elemento 9 se cancelan entre sí. Contarlos duplicaría el
    gasto que ya está en el elemento 6."""
    assert ef.es_reclasificacion("791")
    assert ef.es_reclasificacion("94")
    assert not ef.es_reclasificacion("70")
    assert not ef.es_reclasificacion("7011")


@pytest.mark.parametrize(
    "monto,tasa,monto_es,base,igv,total",
    [
        ("118.00", "18", "total", "100.00", "18.00", "118.00"),
        ("100.00", "18", "base", "100.00", "18.00", "118.00"),
        ("118.00", "0", "total", "118.00", "0.00", "118.00"),
        ("45.50", "0", "neto", "45.50", "0.00", "45.50"),
        # Redondeo: 33.33 / 1.18 no es exacto. El IGV sale por diferencia
        # para que base + igv sea exactamente lo que se cobró.
        ("33.33", "18", "total", "28.25", "5.08", "33.33"),
    ],
)
def test_desagregar_igv(monto, tasa, monto_es, base, igv, total):
    r = plantillas.desagregar(Decimal(monto), Decimal(tasa), monto_es)
    assert r["base"] == Decimal(base)
    assert r["igv"] == Decimal(igv)
    assert r["total"] == Decimal(total)
    assert r["base"] + r["igv"] == r["total"]


def test_toda_plantilla_cuadra_con_y_sin_igv():
    for evento, plantilla in plantillas.PLANTILLAS.items():
        for tasa in (Decimal(0), Decimal(18)):
            importes = plantillas.desagregar(Decimal("100.00"), tasa, plantilla.monto_es)
            debe = sum(
                (importes[linea.importe] for linea in plantilla.lineas if linea.tipo == "debe"),
                Decimal(0),
            )
            haber = sum(
                (importes[linea.importe] for linea in plantilla.lineas if linea.tipo == "haber"),
                Decimal(0),
            )
            assert debe == haber, f"{evento} descuadra con IGV {tasa}"


def test_las_plantillas_solo_usan_cuentas_del_pcge_y_de_ultimo_nivel():
    """Una plantilla que apunte a un rubro imputaría el asiento en la cuenta
    que agrupa, que es justo lo que `crear_asiento_manual` prohíbe."""
    padres = {pcge.padre_de(codigo) for codigo, _ in pcge.CUENTAS}
    for plantilla in plantillas.PLANTILLAS.values():
        for linea in plantilla.lineas:
            assert linea.codigo in pcge.DENOMINACIONES
            assert linea.codigo not in padres


# --- Régimen de IGV (`shared.tributos`) --------------------------------------
class _Empresa:
    """Lo único que `tributos` mira de una empresa."""

    def __init__(self, zona="general", config=None):
        self.zona_tributaria = zona
        self.config_fiscal = config


@pytest.mark.parametrize(
    "zona,config,explicito,esperado",
    [
        # Sin nada elegido manda la zona — el comportamiento histórico, para
        # que desplegar esto no cambie de régimen a ninguna empresa viva.
        ("general", None, None, True),
        ("amazonia_ley27037", None, None, False),
        # Ficha vacia = "segun la zona". Es como el formulario borra el
        # interruptor: el PATCH de organizacion trata `null` como "no lo
        # envie" y conservaria el valor anterior.
        ("amazonia_ley27037", {}, None, False),
        ("general", {}, None, True),
        # La ficha gana sobre la zona: la exoneración de Amazonía depende de
        # zona **y** actividad.
        ("amazonia_ley27037", {"igv_por_defecto": "gravado"}, None, True),
        ("general", {"igv_por_defecto": "exonerado"}, None, False),
        # Un valor que no es ninguna de las dos opciones no se obedece a
        # medias: se ignora y manda la zona (el alta lo rechaza antes).
        ("general", {"igv_por_defecto": "tal vez"}, None, True),
        # La casilla del comprobante gana sobre todo lo demás.
        ("amazonia_ley27037", None, True, True),
        ("general", {"igv_por_defecto": "gravado"}, False, False),
    ],
)
def test_regimen_de_igv(zona, config, explicito, esperado):
    empresa = _Empresa(zona, config)
    assert tributos.gravado(empresa, explicito) is esperado
    assert (tributos.tasa_igv(empresa, explicito) > 0) is esperado


# --- Con base de datos --------------------------------------------------------
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
        s.add_all([almacen, sucursal])
        s.flush()
        ids.update(
            empresa_id=str(empresa.id),
            almacen_id=str(almacen.id),
            sucursal_id=str(sucursal.id),
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


def _regimen(TestSession, ids, *, zona=None, defecto=None):
    """La empresa semilla está en Amazonía (exonerada). `zona` la mueve de
    régimen y `defecto` escribe el interruptor de la ficha
    (`config_fiscal.igv_por_defecto`), que gana sobre la zona."""
    with TestSession() as s:
        empresa = s.get(Empresa, uuid.UUID(ids["empresa_id"]))
        if zona is not None:
            empresa.zona_tributaria = zona
        if defecto is not None:
            empresa.config_fiscal = {tributos.CLAVE_DEFECTO: defecto}
        s.commit()


def _preparar(client, h, ids, *, con_igv=False, TestSession=None):
    if con_igv:
        _regimen(TestSession, ids, zona="general")
    hoy = fechas.hoy()
    client.post(
        "/api/v1/accounting/periodos",
        headers=h,
        json={"empresa_id": ids["empresa_id"], "anio": hoy.year, "mes": hoy.month},
    )
    return client.post(
        f"/api/v1/accounting/cuentas-contables/pcge?empresa_id={ids['empresa_id']}",
        headers=h,
    )


def _cuentas_por_codigo(client, h, ids):
    cuentas = client.get(
        f"/api/v1/accounting/cuentas-contables?empresa_id={ids['empresa_id']}", headers=h
    ).json()
    return {c["codigo"]: c for c in cuentas}


def _lineas_del_asiento(client, h, ids, referencia):
    asientos = client.get(
        f"/api/v1/accounting/asientos?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"]
    generado = [a for a in asientos if a["referencia_origen"] == referencia]
    assert len(generado) == 1, f"se esperaba un asiento para {referencia}"
    lineas = client.get(
        f"/api/v1/accounting/asientos/{generado[0]['id']}/lineas", headers=h
    ).json()
    por_cuenta = {c["id"]: c["codigo"] for c in _cuentas_por_codigo(client, h, ids).values()}
    return {
        (por_cuenta[linea["cuenta_contable_id"]], linea["tipo"]): Decimal(str(linea["monto"]))
        for linea in lineas
    }


def _emitir_comprobante(ids, total, *, gravado=None, tipo="factura"):
    """El evento que publica `sales` al aceptar SUNAT el comprobante. Su
    `referencia_origen` es el comprobante, no la venta: una venta dividida
    emite uno por cuenta."""
    comprobante_id = str(uuid.uuid4())
    accounting_listeners.on_comprobante_emitido(
        {
            "comprobante_id": comprobante_id,
            "venta_id": str(uuid.uuid4()),
            "empresa_id": ids["empresa_id"],
            "tipo": tipo,
            "serie_numero": "F001-00000001",
            "total": total,
            "gravado_igv": gravado,
        }
    )
    return comprobante_id


def _dar_conformidad(TestSession, ids, monto, *, gravado=None):
    """`purchases.comprobante_conforme`. El comprobante tiene que existir de
    verdad: el listener encola además el pago, y `movimiento_dinero` lo
    referencia con FK."""
    with TestSession() as s:
        comprobante = Comprobante(
            empresa_id=uuid.UUID(ids["empresa_id"]),
            compra_id=uuid.uuid4(),
            direccion="recibido",
            tipo="factura",
            serie="F001",
            correlativo=1,
            sustento="movimiento_bancario",
            idempotency_key=f"compra:{uuid.uuid4()}",
            gravado_igv=gravado,
        )
        s.add(comprobante)
        s.commit()
        comprobante_id = str(comprobante.id)

    accounting_listeners.on_comprobante_conforme(
        {
            "comprobante_id": comprobante_id,
            "orden_compra_id": str(uuid.uuid4()),
            "proveedor_id": str(uuid.uuid4()),
            "empresa_id": ids["empresa_id"],
            "condicion_pago": "credito",
            "sujeto_spot": False,
            "porcentaje_deteccion": None,
            "monto": monto,
            "gravado_igv": gravado,
        }
    )
    return comprobante_id


def test_importar_pcge_es_idempotente(env):
    client, ids, _ = env
    h = _token(client)
    primera = _preparar(client, h, ids)
    assert primera.status_code == 201
    assert primera.json()["creadas"] == len(pcge.CUENTAS)

    segunda = client.post(
        f"/api/v1/accounting/cuentas-contables/pcge?empresa_id={ids['empresa_id']}",
        headers=h,
    )
    assert segunda.json()["creadas"] == 0
    assert segunda.json()["existentes"] == len(pcge.CUENTAS)


def test_el_pcge_importado_arma_el_arbol(env):
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)
    cuentas = _cuentas_por_codigo(client, h, ids)
    assert cuentas["40111"]["cuenta_padre_id"] == cuentas["4011"]["id"]
    assert cuentas["4011"]["cuenta_padre_id"] == cuentas["401"]["id"]
    assert cuentas["40"]["cuenta_padre_id"] is None
    assert cuentas["40111"]["tipo"] == "pasivo"
    assert cuentas["7011"]["tipo"] == "ingreso"


def test_no_se_asienta_contra_una_cuenta_que_agrupa_a_otras(env):
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)
    cuentas = _cuentas_por_codigo(client, h, ids)
    r = client.post(
        "/api/v1/accounting/asientos",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "fecha": fechas.hoy().isoformat(),
            "glosa": "Contra el rubro",
            "lineas": [
                {"cuenta_contable_id": cuentas["40"]["id"], "tipo": "debe", "monto": "10.00"},
                {"cuenta_contable_id": cuentas["1041"]["id"], "tipo": "haber", "monto": "10.00"},
            ],
        },
    )
    assert r.status_code == 409
    assert "agrupa" in r.json()["detail"]


def _asientos_de(client, h, ids, referencia):
    asientos = client.get(
        f"/api/v1/accounting/asientos?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"]
    return [a for a in asientos if a["referencia_origen"] == referencia]


def _cuentas_con_movimiento(client, h, ids):
    balance = client.get(
        f"/api/v1/accounting/reportes/balance-comprobacion?empresa_id={ids['empresa_id']}",
        headers=h,
    ).json()
    return {c["codigo"] for c in balance["cuentas"]}


def _confirmar_venta(ids, total):
    venta_id = str(uuid.uuid4())
    accounting_listeners.on_venta_confirmada(
        {
            "venta_id": venta_id,
            "sucursal_id": ids["sucursal_id"],
            "items": [],
            "total": total,
        }
    )
    return venta_id


def _recibir_compra(ids, costo_unitario="20.00", cantidad="10"):
    oc_id = str(uuid.uuid4())
    accounting_listeners.on_compra_recibida(
        {
            "orden_compra_id": oc_id,
            "almacen_destino_id": ids["almacen_id"],
            "items": [{"cantidad": cantidad, "costo_unitario": costo_unitario}],
        }
    )
    return oc_id


def test_la_venta_confirmada_no_asienta_igv(env):
    """El IGV nace con el comprobante. Al confirmar la orden todavía no hay
    documento que diga si la operación va gravada, así que la venta entra
    entera contra el ingreso y el débito fiscal llega después."""
    client, ids, TestSession = env
    h = _token(client)
    _preparar(client, h, ids, con_igv=True, TestSession=TestSession)

    venta_id = _confirmar_venta(ids, "118.00")

    assert _lineas_del_asiento(client, h, ids, venta_id) == {
        ("1212", "debe"): Decimal("118.00"),
        ("7011", "haber"): Decimal("118.00"),
    }


def test_el_comprobante_emitido_reclasifica_el_debito_fiscal(env):
    client, ids, TestSession = env
    h = _token(client)
    _preparar(client, h, ids, con_igv=True, TestSession=TestSession)

    comprobante_id = _emitir_comprobante(ids, "118.00")

    assert _lineas_del_asiento(client, h, ids, comprobante_id) == {
        ("7011", "debe"): Decimal("18.00"),
        ("40111", "haber"): Decimal("18.00"),
    }


def test_venta_exonerada_no_inventa_igv(env):
    """La empresa semilla vende bajo Ley 27037. Desagregar un IGV que nadie
    cobró crearía un pasivo tributario que no existe."""
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)

    venta_id = _confirmar_venta(ids, "118.00")
    _emitir_comprobante(ids, "118.00")

    assert _lineas_del_asiento(client, h, ids, venta_id) == {
        ("1212", "debe"): Decimal("118.00"),
        ("7011", "haber"): Decimal("118.00"),
    }
    # El asiento de IGV ni siquiera se escribe: sus dos líneas valen cero.
    assert "40111" not in _cuentas_con_movimiento(client, h, ids)


def test_el_interruptor_de_la_ficha_gana_sobre_la_zona(env):
    """Una empresa de Amazonía puede tener actividad gravada: la exoneración
    depende de zona **y** actividad, así que el default se elige, no se
    deduce del enum de zona."""
    client, ids, TestSession = env
    h = _token(client)
    _preparar(client, h, ids)
    _regimen(TestSession, ids, defecto=tributos.GRAVADO)

    comprobante_id = _emitir_comprobante(ids, "118.00")

    assert _lineas_del_asiento(client, h, ids, comprobante_id) == {
        ("7011", "debe"): Decimal("18.00"),
        ("40111", "haber"): Decimal("18.00"),
    }


def test_la_casilla_del_comprobante_gana_sobre_el_default(env):
    """La venta puntual fuera de la zona exonerada sí lleva IGV, y la venta
    puntual exonerada dentro de una empresa gravada no lo lleva."""
    client, ids, TestSession = env
    h = _token(client)
    _preparar(client, h, ids)  # empresa exonerada

    gravado = _emitir_comprobante(ids, "118.00", gravado=True)
    assert _lineas_del_asiento(client, h, ids, gravado) == {
        ("7011", "debe"): Decimal("18.00"),
        ("40111", "haber"): Decimal("18.00"),
    }

    _regimen(TestSession, ids, defecto=tributos.GRAVADO)
    exonerado = _emitir_comprobante(ids, "118.00", gravado=False)
    assert _asientos_de(client, h, ids, exonerado) == []


def test_una_nota_de_credito_no_asienta_igv_de_venta(env):
    """Corrige a la baja y tiene su propio evento; usar la plantilla de la
    venta le sumaría débito fiscal en vez de restarlo."""
    client, ids, TestSession = env
    h = _token(client)
    _preparar(client, h, ids, con_igv=True, TestSession=TestSession)

    nc = _emitir_comprobante(ids, "118.00", tipo="nc")

    assert _asientos_de(client, h, ids, nc) == []


def test_compra_recibida_asienta_el_destino_sin_igv(env):
    client, ids, TestSession = env
    h = _token(client)
    _preparar(client, h, ids, con_igv=True, TestSession=TestSession)

    oc_id = _recibir_compra(ids)

    assert _lineas_del_asiento(client, h, ids, oc_id) == {
        ("6011", "debe"): Decimal("200.00"),
        ("4212", "haber"): Decimal("200.00"),
        ("201", "debe"): Decimal("200.00"),
        ("611", "haber"): Decimal("200.00"),
    }


def test_la_conformidad_abre_el_credito_fiscal(env):
    """El crédito fiscal solo se toma con el comprobante válido y anotado
    (marco legal del área), y de paso sube la deuda con el proveedor de la
    base al total de su factura."""
    client, ids, TestSession = env
    h = _token(client)
    _preparar(client, h, ids, con_igv=True, TestSession=TestSession)

    comprobante_id = _dar_conformidad(TestSession, ids, "200.00")

    assert _lineas_del_asiento(client, h, ids, comprobante_id) == {
        ("40111", "debe"): Decimal("36.00"),
        ("4212", "haber"): Decimal("36.00"),
    }


def test_la_empresa_exonerada_que_compra_gravado_registra_su_credito(env):
    """El caso que motivó la casilla: Majambo vende exonerada por Amazonía y
    aun así compra con IGV a un proveedor de fuera de la región."""
    client, ids, TestSession = env
    h = _token(client)
    _preparar(client, h, ids)  # exonerada

    comprobante_id = _dar_conformidad(TestSession, ids, "200.00", gravado=True)

    assert _lineas_del_asiento(client, h, ids, comprobante_id) == {
        ("40111", "debe"): Decimal("36.00"),
        ("4212", "haber"): Decimal("36.00"),
    }


def test_la_regla_de_la_empresa_gana_sobre_la_plantilla(env):
    """La plantilla es el default de fábrica, no una imposición: quien
    configuró su mapeo sigue con el suyo."""
    client, ids, _ = env
    h = _token(client)
    _preparar(client, h, ids)
    cuentas = _cuentas_por_codigo(client, h, ids)
    client.post(
        "/api/v1/accounting/reglas-asiento",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "evento": "sales.venta_confirmada",
            "cuenta_debe_id": cuentas["101"]["id"],
            "cuenta_haber_id": cuentas["7011"]["id"],
        },
    )

    venta_id = str(uuid.uuid4())
    accounting_listeners.on_venta_confirmada(
        {
            "venta_id": venta_id,
            "sucursal_id": ids["sucursal_id"],
            "items": [],
            "total": "50.00",
        }
    )

    lineas = _lineas_del_asiento(client, h, ids, venta_id)
    assert lineas == {
        ("101", "debe"): Decimal("50.00"),
        ("7011", "haber"): Decimal("50.00"),
    }


def test_sin_pcge_importado_el_evento_no_revienta(env):
    """Una empresa que todavía no importó el plan no puede quedarse sin poder
    vender: el asiento se omite y se audita, como siempre."""
    client, ids, _ = env
    h = _token(client)
    hoy = fechas.hoy()
    client.post(
        "/api/v1/accounting/periodos",
        headers=h,
        json={"empresa_id": ids["empresa_id"], "anio": hoy.year, "mes": hoy.month},
    )

    venta_id = str(uuid.uuid4())
    accounting_listeners.on_venta_confirmada(
        {
            "venta_id": venta_id,
            "sucursal_id": ids["sucursal_id"],
            "items": [],
            "total": "50.00",
        }
    )
    asientos = client.get(
        f"/api/v1/accounting/asientos?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"]
    assert [a for a in asientos if a["referencia_origen"] == venta_id] == []


def _con_movimiento(client, h, ids, TestSession):
    """Una compra y una venta, que es el mínimo con el que un balance dice
    algo: activo (mercadería y cobrar), pasivo (proveedor e IGV) y
    resultado."""
    _preparar(client, h, ids, con_igv=True, TestSession=TestSession)
    _recibir_compra(ids)
    _dar_conformidad(TestSession, ids, "200.00")
    _confirmar_venta(ids, "354.00")
    _emitir_comprobante(ids, "354.00")


def test_balance_de_comprobacion_cuadra(env):
    client, ids, TestSession = env
    h = _token(client)
    _con_movimiento(client, h, ids, TestSession)

    r = client.get(
        f"/api/v1/accounting/reportes/balance-comprobacion?empresa_id={ids['empresa_id']}",
        headers=h,
    ).json()
    assert r["cuadra"]
    assert Decimal(str(r["total_debe"])) == Decimal(str(r["total_haber"]))
    por_codigo = {c["codigo"]: c for c in r["cuentas"]}
    assert Decimal(str(por_codigo["201"]["saldo_deudor"])) == Decimal("200.00")
    assert Decimal(str(por_codigo["4212"]["saldo_acreedor"])) == Decimal("236.00")


def test_estado_de_situacion_financiera_cuadra(env):
    client, ids, TestSession = env
    h = _token(client)
    _con_movimiento(client, h, ids, TestSession)

    r = client.get(
        "/api/v1/accounting/reportes/estado-situacion-financiera"
        f"?empresa_id={ids['empresa_id']}",
        headers=h,
    ).json()
    assert r["cuadra"], r["descuadre"]
    assert r["cuentas_sin_clasificar"] == []

    lineas = {
        (seccion["clave"], linea["clave"]): Decimal(str(linea["monto"]))
        for seccion in r["secciones"]
        for linea in seccion["lineas"]
    }
    # Mercadería comprada, cuenta por cobrar de la venta, deuda al proveedor.
    assert lineas[("activo_corriente", "existencias")] == Decimal("200.00")
    assert lineas[("activo_corriente", "cuentas_por_cobrar_comerciales")] == Decimal("354.00")
    assert lineas[("pasivo_corriente", "proveedores")] == Decimal("236.00")
    # IGV: 54 de la venta menos 36 de crédito fiscal de la compra.
    assert lineas[("pasivo_corriente", "tributos")] == Decimal("18.00")
    # Resultado: la venta neta, porque la compra entró al activo (60 contra 61).
    assert lineas[("patrimonio", "resultado_ejercicio")] == Decimal("300.00")


def test_estado_de_resultados_cuadra_contra_el_mayor(env):
    client, ids, TestSession = env
    h = _token(client)
    _con_movimiento(client, h, ids, TestSession)

    r = client.get(
        f"/api/v1/accounting/reportes/estado-resultados?empresa_id={ids['empresa_id']}",
        headers=h,
    ).json()
    assert r["cuadra"]
    assert r["cuentas_sin_clasificar"] == []
    assert Decimal(str(r["resultado_ejercicio"])) == Decimal("300.00")
    assert Decimal(str(r["resultado_libro"])) == Decimal("300.00")

    lineas = {
        linea["clave"]: Decimal(str(linea["monto"]))
        for bloque in r["bloques"]
        for seccion in bloque["secciones"]
        for linea in seccion["lineas"]
    }
    assert lineas["ventas"] == Decimal("300.00")
    # Compras y variación de existencias se anulan: la mercadería sigue en el
    # almacén, todavía no es gasto del ejercicio.
    assert lineas["compras"] == Decimal("200.00")
    assert lineas["variacion_existencias"] == Decimal("-200.00")


def test_libro_mayor_lleva_saldo_corrido(env):
    client, ids, TestSession = env
    h = _token(client)
    _con_movimiento(client, h, ids, TestSession)
    cuentas = _cuentas_por_codigo(client, h, ids)

    r = client.get(
        f"/api/v1/accounting/reportes/libro-mayor?cuenta_id={cuentas['201']['id']}",
        headers=h,
    ).json()
    assert len(r["movimientos"]) == 1
    assert Decimal(str(r["saldo_final"])) == Decimal("200.00")


def test_un_asiento_anulado_y_su_reversion_se_cancelan_en_el_balance(env):
    """Excluir el anulado y dejar la reversión restaría el hecho dos veces —
    por eso el mayor no filtra por estado."""
    client, ids, TestSession = env
    h = _token(client)
    _preparar(client, h, ids, con_igv=True, TestSession=TestSession)

    venta_id = _confirmar_venta(ids, "118.00")
    asientos = client.get(
        f"/api/v1/accounting/asientos?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"]
    asiento_id = [a for a in asientos if a["referencia_origen"] == venta_id][0]["id"]
    client.post(f"/api/v1/accounting/asientos/{asiento_id}/anular", headers=h)

    r = client.get(
        f"/api/v1/accounting/reportes/estado-resultados?empresa_id={ids['empresa_id']}",
        headers=h,
    ).json()
    assert Decimal(str(r["resultado_ejercicio"])) == Decimal("0.00")
