"""Alerta de pedido demorado: el pedido sigue en cocina pasado su umbral.

Lo que protegen estos tests no es el formato de la alerta: es que **no se
avise de más ni de menos**. Alertar por un pedido ya listo es ruido que hace
que dejen de mirar el tablero; no alertar por uno olvidado es el fallo que
esta función existe para evitar.
"""

import datetime
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.sales.application import alertas
from src.modules.sales.infrastructure.models import (
    AlertaPedido,
    ProductoComercial,
    PuntoVenta,
    Venta,
    VentaItem,
)
from src.modules.users.infrastructure.models import (
    Empresa,
    Grupo,
    Marca,
    Sucursal,
    Usuario,
)
from src.modules.users.infrastructure.security import hash_pin
from src.shared.models import ParametroEmpresa

AHORA = datetime.datetime(2026, 8, 4, 15, 0, tzinfo=datetime.UTC)


@pytest.fixture()
def env():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        grupo = Grupo(nombre="Grupo Majambo")
        s.add(grupo)
        s.flush()
        empresa = Empresa(
            grupo_id=grupo.id, razon_social="Majambo EIRL", ruc="20100000001",
            domicilio_fiscal="Jr. X 1", tipo="operativa",
        )
        marca = Marca(grupo_id=grupo.id, nombre="Charlie's", tipo="restaurante")
        s.add_all([empresa, marca])
        s.flush()
        sucursal = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre="CH1",
            direccion="Jr. X 123", tenencia="alquilada",
        )
        s.add(sucursal)
        s.flush()
        pv = PuntoVenta(
            sucursal_id=sucursal.id, canal="trabajador", serie_boleta="B001",
            serie_factura="F001", politica_pago="adelantado",
        )
        producto = ProductoComercial(
            id_interno="P001", marca_id=marca.id, nombre="Pizza"
        )
        cajero = Usuario(
            username="cajero1", pin_hash=hash_pin("654321"), tipo="humano"
        )
        s.add_all([pv, producto, cajero])
        s.flush()
        s.commit()
        yield s, {
            "empresa": empresa,
            "sucursal": sucursal,
            "pv": pv,
            "producto": producto,
            "cajero": cajero,
        }


def _venta(s, ids, *, minutos_atras: int, estados: list[str], estado_venta="pagada"):
    """Venta creada hace N minutos, con sus ítems en los estados dados."""
    venta = Venta(
        sucursal_id=ids["sucursal"].id,
        fecha_orden=AHORA.date(),
        numero_orden=int(uuid.uuid4().int % 100000),
        punto_venta_id=ids["pv"].id,
        canal="pdv",
        modalidad="takeout",
        usuario_id=ids["cajero"].id,
        estado=estado_venta,
        total=Decimal("50.00"),
        idempotency_key=str(uuid.uuid4()),
    )
    s.add(venta)
    s.flush()
    # `created_at` lo pone la base; se fuerza para simular antigüedad.
    venta.created_at = AHORA - datetime.timedelta(minutes=minutos_atras)
    for estado in estados:
        s.add(
            VentaItem(
                venta_id=venta.id,
                producto_comercial_id=ids["producto"].id,
                cantidad=Decimal(1),
                precio_unitario=Decimal("50.00"),
                estado_preparacion=estado,
            )
        )
    s.flush()
    return venta


# --- Cuándo SÍ alerta -------------------------------------------------------
def test_alerta_si_sigue_en_cocina_pasado_el_umbral(env):
    s, ids = env
    venta = _venta(s, ids, minutos_atras=20, estados=["pendiente", "listo"])

    alerta = alertas.revisar_pedido(s, venta.id, ahora=AHORA)

    assert alerta is not None
    assert alerta.minutos_umbral == 15
    assert float(alerta.minutos_transcurridos) == 20
    assert alerta.items_pendientes == 1
    assert alerta.sucursal_id == ids["sucursal"].id


def test_reporta_el_peor_estado_del_pedido(env):
    s, ids = env
    # Uno arrancó y otro ni se tocó: lo grave es que cocina no lo empezó.
    venta = _venta(s, ids, minutos_atras=30, estados=["en_preparacion", "pendiente"])

    alerta = alertas.revisar_pedido(s, venta.id, ahora=AHORA)

    assert alerta.estado_al_alertar == "pendiente"
    assert alerta.items_pendientes == 2


def test_justo_en_el_umbral_alerta(env):
    s, ids = env
    venta = _venta(s, ids, minutos_atras=15, estados=["pendiente"])
    assert alertas.revisar_pedido(s, venta.id, ahora=AHORA) is not None


# --- Cuándo NO alerta -------------------------------------------------------
def test_no_alerta_antes_del_umbral(env):
    s, ids = env
    venta = _venta(s, ids, minutos_atras=14, estados=["pendiente"])
    assert alertas.revisar_pedido(s, venta.id, ahora=AHORA) is None


def test_no_alerta_si_el_pedido_ya_salio(env):
    s, ids = env
    venta = _venta(s, ids, minutos_atras=90, estados=["listo", "entregado"])
    assert alertas.revisar_pedido(s, venta.id, ahora=AHORA) is None


def test_una_venta_anulada_no_se_demora(env):
    s, ids = env
    venta = _venta(
        s, ids, minutos_atras=90, estados=["pendiente"], estado_venta="anulada"
    )
    assert alertas.revisar_pedido(s, venta.id, ahora=AHORA) is None


def test_una_venta_inexistente_no_revienta(env):
    s, _ = env
    assert alertas.revisar_pedido(s, uuid.uuid4(), ahora=AHORA) is None


# --- Idempotencia -----------------------------------------------------------
def test_revisar_dos_veces_no_duplica_la_alerta(env):
    s, ids = env
    venta = _venta(s, ids, minutos_atras=20, estados=["pendiente"])

    primera = alertas.revisar_pedido(s, venta.id, ahora=AHORA)
    segunda = alertas.revisar_pedido(s, venta.id, ahora=AHORA)

    assert primera is not None
    # La segunda no crea nada: es lo que permite que el barrido periódico y
    # la revisión puntual se solapen sin duplicar.
    assert segunda is None
    assert s.scalar(select(AlertaPedido.id).where(AlertaPedido.venta_id == venta.id))
    assert len(list(s.scalars(select(AlertaPedido)))) == 1


# --- Umbral configurable ----------------------------------------------------
def test_el_umbral_lo_manda_parametro_empresa(env):
    s, ids = env
    s.add(
        ParametroEmpresa(
            empresa_id=ids["empresa"].id,
            modulo="sales",
            codigo=alertas.CODIGO_UMBRAL,
            valor={"minutos": 45},
            estado="vigente",
            propuesto_por_id=ids["cajero"].id,
        )
    )
    s.flush()

    # 20 minutos ya no alcanzan con el umbral en 45.
    tardia = _venta(s, ids, minutos_atras=20, estados=["pendiente"])
    assert alertas.revisar_pedido(s, tardia.id, ahora=AHORA) is None

    muy_tardia = _venta(s, ids, minutos_atras=50, estados=["pendiente"])
    alerta = alertas.revisar_pedido(s, muy_tardia.id, ahora=AHORA)
    assert alerta is not None
    # El umbral se congela en la fila: subirlo mañana no reescribe esto.
    assert alerta.minutos_umbral == 45


# --- Barrido ----------------------------------------------------------------
def test_el_barrido_levanta_lo_que_la_revision_puntual_perdio(env):
    s, ids = env
    demorada = _venta(s, ids, minutos_atras=40, estados=["pendiente"])
    otra_demorada = _venta(s, ids, minutos_atras=25, estados=["en_preparacion"])
    _venta(s, ids, minutos_atras=5, estados=["pendiente"])  # a tiempo
    _venta(s, ids, minutos_atras=99, estados=["entregado"])  # ya salió

    alertas_creadas = alertas.barrer(s, ahora=AHORA)

    assert {a.venta_id for a in alertas_creadas} == {demorada.id, otra_demorada.id}


def test_el_barrido_es_idempotente(env):
    s, ids = env
    _venta(s, ids, minutos_atras=40, estados=["pendiente"])

    assert len(alertas.barrer(s, ahora=AHORA)) == 1
    assert alertas.barrer(s, ahora=AHORA) == []
    assert len(list(s.scalars(select(AlertaPedido)))) == 1


# --- Cierre -----------------------------------------------------------------
def test_atender_cierra_la_alerta_una_sola_vez(env):
    s, ids = env
    venta = _venta(s, ids, minutos_atras=20, estados=["pendiente"])
    alerta = alertas.revisar_pedido(s, venta.id, ahora=AHORA)

    alertas.atender(s, alerta.id, ids["cajero"].id, "se avisó a cocina")
    s.flush()
    primera_marca = alerta.atendida_at
    assert primera_marca is not None
    assert alerta.nota == "se avisó a cocina"

    # Atender de nuevo no pisa quién la atendió primero.
    alertas.atender(s, alerta.id, uuid.uuid4(), "otra nota")
    assert alerta.atendida_por == ids["cajero"].id
    assert alerta.nota == "se avisó a cocina"
