"""Estimado de espera del sitio de marca (RN-WEB-011): sale de lo que se pide,
no de una base fija. Una botella de agua no tarda lo que seis pizzas.
"""

from src.modules.storefront.domain.asignacion import estimar_eta

POR_PEDIDO = 5


def test_lo_que_sale_al_instante_no_espera_la_cola():
    # Seis pedidos delante, pero no hay nada que cocinar: piso de 5 min.
    assert estimar_eta(6, preparacion_min=0, minutos_por_pedido=POR_PEDIDO) == (5, 10)


def test_pizza_con_la_cocina_vacia():
    assert estimar_eta(0, preparacion_min=25, minutos_por_pedido=POR_PEDIDO) == (25, 40)


def test_pizza_con_cuatro_pedidos_delante():
    assert estimar_eta(4, preparacion_min=25, minutos_por_pedido=POR_PEDIDO) == (45, 60)


def test_delivery_suma_el_trayecto():
    eta = estimar_eta(0, preparacion_min=25, minutos_por_pedido=POR_PEDIDO, viaje_min=9)
    assert eta == (34, 49)


def test_delivery_de_algo_sin_cocina_es_solo_el_trayecto():
    eta = estimar_eta(3, preparacion_min=0, minutos_por_pedido=POR_PEDIDO, viaje_min=9)
    assert eta == (9, 14)


def test_preparacion_corta_usa_el_colchon_de_mostrador():
    # Menos de 20 min no pasa por horno: colchón de 5, no de 15.
    assert estimar_eta(0, preparacion_min=10, minutos_por_pedido=POR_PEDIDO) == (10, 15)
