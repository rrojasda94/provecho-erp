"""La reposición por venta anulada entra al lote del que salió, no al del
día (ADR-094).

`movimiento_inventario.referencia` ya guardaba el `venta_id` en cada salida
—incluida la que reparte por FEFO entre varios lotes (ADR-015)— así que
`inventory.application.listeners._reponer` reconstruye de cuáles lotes
salió sin que el evento tenga que transportar nada nuevo. Se prueba a nivel
de aplicación y no por HTTP: lo que cambió vive en `_lotes_de_la_salida` y
`_reponer`, y `stock_uc.registrar_salida`/`registrar_movimiento` ya tienen
su propio suite en `test_lotes.py`.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.inventory.application import listeners
from src.modules.inventory.application import lotes as lotes_uc
from src.modules.inventory.application import stock as stock_uc
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    Sku,
    Stock,
    StockLote,
    UnidadMedida,
)
from src.modules.users.infrastructure.models import Almacen, Empresa, Grupo
from src.shared import fechas

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

HOY = fechas.hoy()


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def base(session):
    grupo = Grupo(nombre="Grupo Majambo")
    session.add(grupo)
    session.flush()
    empresa = Empresa(
        grupo_id=grupo.id,
        razon_social="Majambo EIRL",
        ruc="20450311520",
        domicilio_fiscal="Tarapoto",
        tipo="operativa",
        zona_tributaria="amazonia_ley27037",
    )
    cat_udm = CategoriaUdm(nombre="Peso")
    session.add_all([empresa, cat_udm])
    session.flush()
    udm = UnidadMedida(categoria_udm_id=cat_udm.id, nombre="Kilo", ratio=Decimal(1))
    session.add(udm)
    session.flush()
    almacen = Almacen(empresa_id=empresa.id, nombre="Central", tipo="central")
    queso = Articulo(
        empresa_id=empresa.id, id_interno="Q001", nombre="Queso",
        unidad_medida_id=udm.id, tipo="insumo", controla_lote=True,
    )
    session.add_all([almacen, queso])
    session.flush()
    sku = Sku(articulo_id=queso.id, codigo="SKU-QUESO")
    session.add(sku)
    session.flush()
    return {"empresa": empresa, "almacen": almacen, "articulo": queso, "sku": sku}


def _lote(session, base, codigo, dias_a_vencer=None):
    vencimiento = HOY + timedelta(days=dias_a_vencer) if dias_a_vencer else None
    lote = lotes_uc.crear_lote(
        session, articulo_id=base["articulo"].id, codigo=codigo,
        fecha_vencimiento=vencimiento,
    )
    session.flush()
    return lote


def _ingresar(session, base, lote_id, cantidad):
    stock_uc.registrar_movimiento(
        session, almacen_id=base["almacen"].id, sku_id=base["sku"].id,
        cantidad=cantidad, tipo="recepcion_compra", lote_id=lote_id,
    )
    session.flush()


def _salir(session, base, cantidad, venta_id):
    stock_uc.registrar_salida(
        session, almacen_id=base["almacen"].id, sku_id=base["sku"].id,
        cantidad=cantidad, tipo="consumo_venta", referencia=venta_id,
    )
    session.flush()


def _reponer(session, base, cantidad, venta_id):
    listeners._reponer(
        session, almacen_id=base["almacen"].id, sku_id=base["sku"].id,
        cantidad=cantidad, tipo="devolucion", venta_id=venta_id,
    )
    session.flush()


def _stock_del_lote(session, base, lote_id):
    fila = session.scalar(
        select(StockLote).where(
            StockLote.almacen_id == base["almacen"].id,
            StockLote.sku_id == base["sku"].id,
            StockLote.lote_id == lote_id,
        )
    )
    return fila.cantidad if fila else Decimal(0)


def test_reponer_vuelve_al_mismo_lote_cuando_hay_uno_solo(session, base):
    lote = _lote(session, base, "L1")
    _ingresar(session, base, lote.id, Decimal(10))
    _salir(session, base, Decimal(6), "venta-1")
    assert _stock_del_lote(session, base, lote.id) == Decimal(4)

    _reponer(session, base, Decimal(6), "venta-1")
    assert _stock_del_lote(session, base, lote.id) == Decimal(10)


def test_reponer_total_reparte_entre_los_lotes_como_salio(session, base):
    """FEFO se llevó 5 del lote que vencía antes y 3 del que vencía
    después; una anulación total tiene que devolver exactamente eso a cada
    uno, no juntar los 8 en un lote nuevo."""
    lote_a = _lote(session, base, "A", dias_a_vencer=5)
    lote_b = _lote(session, base, "B", dias_a_vencer=20)
    _ingresar(session, base, lote_a.id, Decimal(5))
    _ingresar(session, base, lote_b.id, Decimal(5))

    _salir(session, base, Decimal(8), "venta-2")
    assert _stock_del_lote(session, base, lote_a.id) == Decimal(0)
    assert _stock_del_lote(session, base, lote_b.id) == Decimal(2)

    _reponer(session, base, Decimal(8), "venta-2")
    assert _stock_del_lote(session, base, lote_a.id) == Decimal(5)
    assert _stock_del_lote(session, base, lote_b.id) == Decimal(5)


def test_reponer_parcial_prioriza_el_lote_que_vencia_antes(session, base):
    """Una nota de crédito por menos de lo vendido: entra primero a donde
    salió primero (el que vencía antes), sin pasarse de lo que ese lote
    entregó."""
    lote_a = _lote(session, base, "A", dias_a_vencer=5)
    lote_b = _lote(session, base, "B", dias_a_vencer=20)
    _ingresar(session, base, lote_a.id, Decimal(5))
    _ingresar(session, base, lote_b.id, Decimal(5))
    _salir(session, base, Decimal(8), "venta-3")  # 5 de A + 3 de B

    _reponer(session, base, Decimal(4), "venta-3")
    assert _stock_del_lote(session, base, lote_a.id) == Decimal(4)  # 0 + 4
    assert _stock_del_lote(session, base, lote_b.id) == Decimal(2)  # sin tocar


def test_reponer_parcial_que_excede_el_primer_lote_sigue_al_segundo(session, base):
    lote_a = _lote(session, base, "A", dias_a_vencer=5)
    lote_b = _lote(session, base, "B", dias_a_vencer=20)
    _ingresar(session, base, lote_a.id, Decimal(5))
    _ingresar(session, base, lote_b.id, Decimal(5))
    _salir(session, base, Decimal(8), "venta-4")  # 5 de A + 3 de B

    _reponer(session, base, Decimal(6), "venta-4")
    assert _stock_del_lote(session, base, lote_a.id) == Decimal(5)  # 0 + 5 (tope)
    assert _stock_del_lote(session, base, lote_b.id) == Decimal(3)  # 2 + 1


def test_reponer_sin_rastro_cae_al_lote_del_dia(session, base):
    """Venta anterior a este cambio, o el SKU no dejó rastro por otro
    motivo: mismo comportamiento de siempre — no falla, entra a un lote
    nuevo."""
    _reponer(session, base, Decimal(3), "venta-sin-historia")

    total = session.scalar(
        select(StockLote).where(
            StockLote.almacen_id == base["almacen"].id,
            StockLote.sku_id == base["sku"].id,
        )
    )
    assert total is not None
    assert total.cantidad == Decimal(3)


def test_reponer_articulo_sin_control_de_lote_no_cambia(session, base):
    """El camino de siempre para lo que no controla lote: un solo
    movimiento, sin lote — `_lotes_de_la_salida` no encuentra nada porque
    la salida original tampoco dejó `lote_id`."""
    base["articulo"].controla_lote = False
    session.flush()
    stock_uc.registrar_movimiento(
        session, almacen_id=base["almacen"].id, sku_id=base["sku"].id,
        cantidad=Decimal(10), tipo="recepcion_compra",
    )
    stock_uc.registrar_salida(
        session, almacen_id=base["almacen"].id, sku_id=base["sku"].id,
        cantidad=Decimal(4), tipo="consumo_venta", referencia="venta-5",
    )
    session.flush()

    _reponer(session, base, Decimal(4), "venta-5")

    # Sin lote, la cantidad vive en `stock`, no en `stock_lote`.
    fila = session.scalar(
        select(Stock).where(
            Stock.almacen_id == base["almacen"].id, Stock.sku_id == base["sku"].id
        )
    )
    assert fila.cantidad == Decimal(10)  # 10 - 4 + 4
