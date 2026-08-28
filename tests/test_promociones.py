"""Motor de promociones condicionales (ADR-076).

Las reglas son puras, así que la mayoría de los casos se prueban sin base:
entra lo que el pedido lleva, sale cuánto se descuenta. Los últimos ejercitan
la frontera que este slice no puede cruzar — que una promoción **nunca**
escriba en `venta.descuento_*`, que es el descuento manual firmado.
"""

import uuid
from datetime import date, time
from decimal import Decimal

import pytest

from src.modules.sales.domain import promociones as promo

PIZZA = "p-pizza"
GASEOSA = "p-gaseosa"
PAPAS = "p-papas"
CAT_PIZZAS = "c-pizzas"
CAT_BEBIDAS = "c-bebidas"


def linea(producto, precio, cantidad=1, categoria=None, id_=None):
    return promo.LineaPromocionable(
        venta_item_id=id_ or f"i-{producto}-{precio}-{cantidad}",
        producto_id=producto,
        categoria_id=categoria,
        cantidad=cantidad,
        precio_unitario=Decimal(str(precio)),
    )


def regla(tipo, condicion, beneficio, **extra):
    return promo.Regla(
        id=extra.pop("id", str(uuid.uuid4())),
        nombre=extra.pop("nombre", "Promo"),
        tipo=tipo,
        condicion=condicion,
        beneficio=beneficio,
        **extra,
    )


# --- N×M ----------------------------------------------------------------------
def test_2x1_regala_una_de_cada_dos():
    r = regla("nxm", {"categoria_ids": [CAT_PIZZAS], "lleva": 2}, {"libera": 1})
    aplicadas = promo.aplicar([r], [linea(PIZZA, "30.00", 2, CAT_PIZZAS)])

    assert promo.total_promociones(aplicadas) == Decimal("30.00")


def test_2x1_se_repite_mientras_alcance():
    """Seis pizzas con un 2x1 son tres regaladas, no una: el turno que pide
    para una mesa larga no tiene por qué partir el pedido en tres."""
    r = regla("nxm", {"categoria_ids": [CAT_PIZZAS], "lleva": 2}, {"libera": 1})
    aplicadas = promo.aplicar([r], [linea(PIZZA, "30.00", 6, CAT_PIZZAS)])

    assert promo.total_promociones(aplicadas) == Decimal("90.00")


def test_la_segunda_a_mitad_de_precio_es_un_nxm_con_porcentaje():
    """El beneficio es un % sobre lo liberado, no un booleano de "gratis":
    sin eso, la promoción más común del rubro necesitaría su propio tipo."""
    r = regla(
        "nxm",
        {"categoria_ids": [CAT_PIZZAS], "lleva": 2},
        {"libera": 1, "descuento_pct": 50},
    )
    aplicadas = promo.aplicar([r], [linea(PIZZA, "30.00", 2, CAT_PIZZAS)])

    assert promo.total_promociones(aplicadas) == Decimal("15.00")


def test_el_2x1_regala_la_mas_barata():
    """Entre una familiar y una personal se libera la personal. Al revés, la
    promoción costaría más de lo que ninguna carta del rubro promete."""
    r = regla("nxm", {"categoria_ids": [CAT_PIZZAS], "lleva": 2}, {"libera": 1})
    aplicadas = promo.aplicar(
        [r],
        [
            linea(PIZZA, "50.00", 1, CAT_PIZZAS, id_="familiar"),
            linea(PIZZA, "20.00", 1, CAT_PIZZAS, id_="personal"),
        ],
    )

    assert promo.total_promociones(aplicadas) == Decimal("20.00")


def test_una_sola_pizza_no_activa_el_2x1():
    r = regla("nxm", {"categoria_ids": [CAT_PIZZAS], "lleva": 2}, {"libera": 1})

    assert promo.aplicar([r], [linea(PIZZA, "30.00", 1, CAT_PIZZAS)]) == []


def test_la_gaseosa_no_entra_en_el_2x1_de_pizzas():
    r = regla("nxm", {"categoria_ids": [CAT_PIZZAS], "lleva": 2}, {"libera": 1})
    aplicadas = promo.aplicar(
        [r],
        [
            linea(PIZZA, "30.00", 1, CAT_PIZZAS),
            linea(GASEOSA, "6.00", 3, CAT_BEBIDAS),
        ],
    )

    assert aplicadas == []


# --- Cantidad -----------------------------------------------------------------
def test_desde_x_unidades_de_una_categoria_baja_un_porcentaje():
    r = regla(
        "cantidad",
        {"categoria_ids": [CAT_BEBIDAS], "minimo": 6},
        {"descuento_pct": 15},
    )
    aplicadas = promo.aplicar([r], [linea(GASEOSA, "6.00", 6, CAT_BEBIDAS)])

    # 15% sobre 36.00
    assert promo.total_promociones(aplicadas) == Decimal("5.40")


def test_por_debajo_del_minimo_no_pasa_nada():
    r = regla(
        "cantidad",
        {"categoria_ids": [CAT_BEBIDAS], "minimo": 6},
        {"descuento_pct": 15},
    )

    assert promo.aplicar([r], [linea(GASEOSA, "6.00", 5, CAT_BEBIDAS)]) == []


# --- Combo --------------------------------------------------------------------
def test_el_combo_exige_todos_sus_productos():
    r = regla("combo", {"producto_ids": [PIZZA, PAPAS, GASEOSA]}, {"precio_fijo": "40.00"})
    completo = [
        linea(PIZZA, "30.00", 1, CAT_PIZZAS),
        linea(PAPAS, "12.00", 1),
        linea(GASEOSA, "6.00", 1, CAT_BEBIDAS),
    ]

    # 48.00 de lista → 40.00
    assert promo.total_promociones(promo.aplicar([r], completo)) == Decimal("8.00")
    assert promo.aplicar([r], completo[:2]) == []


def test_el_combo_puede_regalar_uno_de_sus_productos():
    r = regla(
        "combo",
        {"producto_ids": [PIZZA, GASEOSA]},
        {"gratis_producto_id": GASEOSA},
    )
    aplicadas = promo.aplicar(
        [r],
        [linea(PIZZA, "30.00", 1, CAT_PIZZAS), linea(GASEOSA, "6.00", 1, CAT_BEBIDAS)],
    )

    assert promo.total_promociones(aplicadas) == Decimal("6.00")


# --- Monto mínimo -------------------------------------------------------------
def test_desde_un_monto_minimo_baja_el_total():
    r = regla("monto_minimo", {"minimo": "80.00"}, {"descuento_pct": 10})
    aplicadas = promo.aplicar(
        [r],
        [linea(PIZZA, "30.00", 3, CAT_PIZZAS)],
    )

    assert promo.total_promociones(aplicadas) == Decimal("9.00")


def test_por_debajo_del_monto_minimo_no_baja_nada():
    r = regla("monto_minimo", {"minimo": "80.00"}, {"descuento_pct": 10})

    assert promo.aplicar([r], [linea(PIZZA, "30.00", 2, CAT_PIZZAS)]) == []


def test_el_precio_de_franja_es_un_monto_minimo_en_cero():
    """"El martes de pizzas" no pone condición sobre lo que el cliente lleva,
    solo sobre cuándo lo lleva: eso lo expresa la vigencia, y la condición
    queda vacía."""
    r = regla(
        "monto_minimo",
        {"categoria_ids": [CAT_PIZZAS], "minimo": 0},
        {"descuento_pct": 20},
    )
    aplicadas = promo.aplicar([r], [linea(PIZZA, "30.00", 1, CAT_PIZZAS)])

    assert promo.total_promociones(aplicadas) == Decimal("6.00")


# --- Solapes ------------------------------------------------------------------
def test_dos_promociones_no_cobran_la_misma_pizza():
    """Un 2x1 y un 20% sobre pizzas se activarían los dos sobre las mismas
    unidades, y el local regalaría más de lo que aprobó. Gana la de mayor
    prioridad y la otra se queda sin unidades."""
    dos_por_uno = regla(
        "nxm",
        {"categoria_ids": [CAT_PIZZAS], "lleva": 2},
        {"libera": 1},
        prioridad=10,
        nombre="2x1",
    )
    veinte = regla(
        "monto_minimo",
        {"categoria_ids": [CAT_PIZZAS], "minimo": 0},
        {"descuento_pct": 20},
        prioridad=1,
        nombre="20% en pizzas",
    )
    aplicadas = promo.aplicar([dos_por_uno, veinte], [linea(PIZZA, "30.00", 2, CAT_PIZZAS)])

    assert [a.nombre for a in aplicadas] == ["2x1"]
    assert promo.total_promociones(aplicadas) == Decimal("30.00")


def test_la_acumulable_se_suma_sobre_lo_que_quede():
    dos_por_uno = regla(
        "nxm",
        {"categoria_ids": [CAT_PIZZAS], "lleva": 2},
        {"libera": 1},
        prioridad=10,
        nombre="2x1",
    )
    acumulable = regla(
        "monto_minimo",
        {"minimo": 0},
        {"descuento_pct": 10},
        prioridad=1,
        acumulable=True,
        nombre="10% socio",
    )
    aplicadas = promo.aplicar(
        [dos_por_uno, acumulable], [linea(PIZZA, "30.00", 2, CAT_PIZZAS)]
    )

    assert sorted(a.nombre for a in aplicadas) == ["10% socio", "2x1"]


def test_la_acumulable_no_le_reserva_unidades_a_nadie():
    """Se evalúa sobre lo que quede y no marca nada como usado: si reservara,
    un "10 % sobre todo" impediría que el 2x1 se activara después."""
    acumulable = regla(
        "monto_minimo",
        {"minimo": 0},
        {"descuento_pct": 10},
        prioridad=99,
        acumulable=True,
        nombre="10% socio",
    )
    dos_por_uno = regla(
        "nxm",
        {"categoria_ids": [CAT_PIZZAS], "lleva": 2},
        {"libera": 1},
        prioridad=1,
        nombre="2x1",
    )
    aplicadas = promo.aplicar(
        [acumulable, dos_por_uno], [linea(PIZZA, "30.00", 2, CAT_PIZZAS)]
    )

    assert sorted(a.nombre for a in aplicadas) == ["10% socio", "2x1"]


# --- Vigencia -----------------------------------------------------------------
MARTES = date(2026, 8, 25)
MIERCOLES = date(2026, 8, 26)


@pytest.mark.parametrize(
    ("dia", "hora", "espera"),
    [
        (MARTES, time(20, 0), True),
        (MIERCOLES, time(20, 0), False),  # otro día de la semana
        (MARTES, time(10, 0), False),  # fuera de la franja
    ],
)
def test_el_martes_de_pizzas_corre_solo_los_martes_de_noche(dia, hora, espera):
    assert (
        promo.vigente(
            desde=None,
            hasta=None,
            dias_semana=[1],
            hora_desde=time(18, 0),
            hora_hasta=time(23, 0),
            dia=dia,
            hora=hora,
        )
        is espera
    )


def test_la_franja_puede_cruzar_la_medianoche():
    """Un happy hour de 22:00 a 02:00 es un caso real, y compararlo como un
    rango simple lo dejaría siempre fuera."""
    argumentos = dict(
        desde=None, hasta=None, dias_semana=None,
        hora_desde=time(22, 0), hora_hasta=time(2, 0), dia=MARTES,
    )

    assert promo.vigente(**argumentos, hora=time(23, 30)) is True
    assert promo.vigente(**argumentos, hora=time(1, 0)) is True
    assert promo.vigente(**argumentos, hora=time(12, 0)) is False


def test_fuera_del_rango_de_fechas_no_corre():
    argumentos = dict(
        dias_semana=None, hora_desde=None, hora_hasta=None, hora=time(12, 0)
    )

    assert promo.vigente(desde=MIERCOLES, hasta=None, dia=MARTES, **argumentos) is False
    assert promo.vigente(desde=None, hasta=MARTES, dia=MIERCOLES, **argumentos) is False
    assert promo.vigente(desde=MARTES, hasta=MIERCOLES, dia=MARTES, **argumentos) is True
