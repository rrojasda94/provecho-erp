"""Cuándo volver a comprar: consumo promedio y fecha en que se toca el mínimo."""

from datetime import date
from decimal import Decimal

from src.modules.inventory.domain import rules

HOY = date(2026, 9, 23)


def test_consumo_diario_necesita_una_semana_de_historia():
    assert rules.consumo_diario(Decimal(60), 6) is None
    assert rules.consumo_diario(Decimal(70), 7) == Decimal(10)


def test_consumo_diario_se_mide_en_la_ventana_de_90_dias():
    # 900 salidas en la ventana, aunque el artículo tenga un año de historia.
    assert rules.consumo_diario(Decimal(900), 365) == Decimal(10)


def test_proxima_compra_es_cuando_el_stock_toca_el_minimo():
    # 100 en stock, mínimo 30, salen 10 por día: 7 días de margen.
    assert rules.proxima_compra(Decimal(100), Decimal(30), Decimal(10), HOY) == date(2026, 9, 30)


def test_sin_minimo_se_proyecta_contra_cero():
    assert rules.proxima_compra(Decimal(50), None, Decimal(10), HOY) == date(2026, 9, 28)


def test_en_el_minimo_o_debajo_es_hoy():
    assert rules.proxima_compra(Decimal(20), Decimal(30), Decimal(10), HOY) == HOY


def test_sin_consumo_no_hay_fecha():
    assert rules.proxima_compra(Decimal(100), Decimal(30), None, HOY) is None
    assert rules.proxima_compra(Decimal(100), Decimal(30), Decimal(0), HOY) is None
