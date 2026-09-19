"""Opciones de una línea del carrito del sitio (extras y sabores, Mitad x Mitad):
las reglas puras que se hacen cumplir ANTES de cobrar (RN-COM-021/023/038/040,
RN-WEB-017)."""

import uuid
from decimal import Decimal

import pytest

from src.modules.storefront.domain.opciones import (
    AtributoOfrecido,
    ExtraOfrecido,
    GrupoOfrecido,
    OpcionesNodo,
    ValorOfrecido,
    evaluar,
)

QUESO = uuid.uuid4()
TOCINO = uuid.uuid4()
CHAMPI = uuid.uuid4()
SABOR_A = uuid.uuid4()
SABOR_B = uuid.uuid4()
GRUPO_SABOR = uuid.uuid4()
H1, P1 = uuid.uuid4(), uuid.uuid4()  # Mitad 1: hawaiana, peperoni
H2, P2 = uuid.uuid4(), uuid.uuid4()  # Mitad 2


def _extra(id_, nombre, precio, maximo=None, grupo=None):
    return ExtraOfrecido(id_, nombre, Decimal(precio), maximo, grupo)


def _mitad_y_mitad():
    return OpcionesNodo(
        extras={
            QUESO: _extra(QUESO, "Extra queso", "6.00", maximo=2),
            TOCINO: _extra(TOCINO, "Extra tocino", "8.00"),
            CHAMPI: _extra(CHAMPI, "Extra champiñones", "5.00"),
        },
        atributos=(
            AtributoOfrecido(
                "Mitad 1",
                {
                    H1: ValorOfrecido("Hawaiana", Decimal("3.00")),
                    P1: ValorOfrecido("Peperoni", Decimal(0)),
                },
            ),
            AtributoOfrecido(
                "Mitad 2",
                {
                    H2: ValorOfrecido("Hawaiana", Decimal(0)),
                    P2: ValorOfrecido("Peperoni", Decimal(0)),
                },
            ),
        ),
        # No se repite el mismo sabor en las dos mitades: sería una entera.
        exclusiones=frozenset({frozenset({H1, H2}), frozenset({P1, P2})}),
    )


def test_mitad_y_mitad_con_extras_suma_recargo_y_extras_por_unidad():
    r = evaluar(_mitad_y_mitad(), ((QUESO, 2), (TOCINO, 1)), (H1, P2))
    assert r.recargo_valores == Decimal("3.00")
    assert r.extras_por_unidad == Decimal("20.00")  # 2 x 6 + 1 x 8
    assert [v.nombre for _, v in r.valores] == ["Hawaiana", "Peperoni"]


def test_sin_opciones_es_una_linea_de_siempre():
    r = evaluar(OpcionesNodo(), (), ())
    assert r.recargo_valores == 0 and r.extras_por_unidad == 0


@pytest.mark.parametrize(
    ("extras", "valores", "mensaje"),
    [
        ((), (H1,), "falta elegir Mitad 2"),
        ((), (), "falta elegir Mitad 1"),
        ((), (H1, P1, P2), "una sola opción de Mitad 1"),
        ((), (H1, H2), "esa combinación no se puede pedir"),
        ((), (P1, P2), "esa combinación no se puede pedir"),
        ((), (H1, uuid.uuid4()), "ya no se ofrece"),
        ((), (H1, H1), "no puede repetirse"),
        (((uuid.uuid4(), 1),), (H1, P2), "ya no se ofrece"),
        (((QUESO, 3),), (H1, P2), "admite hasta 2"),
        (((QUESO, 1), (QUESO, 1)), (H1, P2), "no puede repetirse"),
        (((QUESO, 2), (TOCINO, 1), (CHAMPI, 1)), (H1, P2), "máximo 3 extras"),
    ],
)
def test_lo_que_sales_rechazaria_se_rechaza_antes_de_cobrar(extras, valores, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        evaluar(_mitad_y_mitad(), extras, valores)


def _con_sabor_obligatorio():
    """Como la demo: el sabor es un extra de un grupo de mínimo 1 y máximo 1."""
    return OpcionesNodo(
        extras={
            SABOR_A: _extra(SABOR_A, "Peperoni", "0.00", grupo=GRUPO_SABOR),
            SABOR_B: _extra(SABOR_B, "Hawaiana", "0.00", grupo=GRUPO_SABOR),
            QUESO: _extra(QUESO, "Extra queso", "6.00"),
            TOCINO: _extra(TOCINO, "Extra tocino", "8.00"),
            CHAMPI: _extra(CHAMPI, "Extra champiñones", "5.00"),
        },
        grupos={GRUPO_SABOR: GrupoOfrecido(GRUPO_SABOR, "Sabor", 1, 1)},
    )


def test_un_grupo_obligatorio_exige_elegir_y_respeta_su_maximo():
    with pytest.raises(ValueError, match="falta elegir Sabor"):
        evaluar(_con_sabor_obligatorio(), ((QUESO, 1),), ())
    with pytest.raises(ValueError, match="Sabor admite hasta 1"):
        evaluar(_con_sabor_obligatorio(), ((SABOR_A, 1), (SABOR_B, 1)), ())
    assert evaluar(_con_sabor_obligatorio(), ((SABOR_A, 1),), ()).extras_por_unidad == 0


def test_el_sabor_del_grupo_no_cuenta_para_el_tope_de_extras_de_pago():
    # 3 extras de pago + el sabor obligatorio: el sabor es parte de la pizza.
    r = evaluar(
        _con_sabor_obligatorio(),
        ((SABOR_A, 1), (QUESO, 1), (TOCINO, 1), (CHAMPI, 1)),
        (),
    )
    assert r.extras_por_unidad == Decimal("19.00")
    with pytest.raises(ValueError, match="máximo 3 extras"):
        extras = ((SABOR_A, 1), (QUESO, 2), (TOCINO, 1), (CHAMPI, 1))
        evaluar(_con_sabor_obligatorio(), extras, ())
