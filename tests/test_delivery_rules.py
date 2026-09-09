"""Reglas puras del reparto propio (ADR-098): transiciones de entrega y
ruta, heurística de ruteo y ETA acumulado. Sin infraestructura — nada de
esto abre una sesión."""

from datetime import UTC, datetime
from decimal import Decimal

from src.modules.delivery.domain import rules


# --- Transiciones de entrega --------------------------------------------------
def test_una_entrega_pendiente_se_puede_asignar():
    assert rules.puede_asignar_a_ruta("pendiente") is True
    assert rules.puede_asignar_a_ruta("asignada") is False


def test_solo_una_entrega_en_ruta_se_entrega_o_falla():
    for estado in rules.ESTADOS_ENTREGA:
        assert rules.puede_entregar(estado) is (estado == "en_ruta")
        assert rules.puede_fallar(estado) is (estado == "en_ruta")


def test_solo_una_entrega_fallida_se_reintenta():
    for estado in rules.ESTADOS_ENTREGA:
        assert rules.puede_reintentar(estado) is (estado == "fallida")


def test_se_cierra_una_entrega_pendiente_o_fallida_no_una_en_ruta():
    assert rules.puede_cerrar_entrega("pendiente") is True
    assert rules.puede_cerrar_entrega("fallida") is True
    assert rules.puede_cerrar_entrega("en_ruta") is False
    assert rules.puede_cerrar_entrega("entregada") is False


def test_la_anulacion_solo_cancela_sola_antes_de_salir_a_ruta():
    assert rules.cancela_sola_por_anulacion("pendiente") is True
    assert rules.cancela_sola_por_anulacion("asignada") is True
    assert rules.cancela_sola_por_anulacion("en_ruta") is False
    assert rules.cancela_sola_por_anulacion("entregada") is False


def test_motivo_otro_exige_detalle():
    assert rules.motivo_requiere_detalle("otro") is True
    for motivo in rules.MOTIVOS_FALLO:
        if motivo != "otro":
            assert rules.motivo_requiere_detalle(motivo) is False


# --- Transiciones de ruta ------------------------------------------------------
def test_una_ruta_necesita_al_menos_una_parada_para_iniciar():
    assert rules.puede_iniciar_ruta("planificada", 0) is False
    assert rules.puede_iniciar_ruta("planificada", 1) is True
    assert rules.puede_iniciar_ruta("en_curso", 1) is False


def test_solo_se_cancela_una_ruta_planificada():
    assert rules.puede_cancelar_ruta("planificada") is True
    assert rules.puede_cancelar_ruta("en_curso") is False


def test_una_ruta_finaliza_solo_con_todas_las_paradas_resueltas():
    assert rules.puede_finalizar_ruta("en_curso", ["entregada", "fallida"]) is True
    assert rules.puede_finalizar_ruta("en_curso", ["entregada", "en_ruta"]) is False
    assert rules.puede_finalizar_ruta("planificada", ["entregada"]) is False
    assert rules.puede_finalizar_ruta("en_curso", ["cancelada"]) is True


def test_cantidad_de_paradas_dentro_del_limite():
    assert rules.cantidad_de_paradas_valida(0, 10) is False
    assert rules.cantidad_de_paradas_valida(1, 10) is True
    assert rules.cantidad_de_paradas_valida(10, 10) is True
    assert rules.cantidad_de_paradas_valida(11, 10) is False


# --- Posición ------------------------------------------------------------------
def test_la_posicion_solo_se_acepta_con_la_ruta_en_curso():
    assert rules.acepta_posicion("en_curso") is True
    assert rules.acepta_posicion("planificada") is False
    assert rules.acepta_posicion("finalizada") is False


def test_la_posicion_solo_se_expone_con_la_entrega_en_ruta():
    assert rules.expone_posicion("en_ruta") is True
    for estado in rules.ESTADOS_ENTREGA:
        if estado != "en_ruta":
            assert rules.expone_posicion(estado) is False


# --- Heurística de ruteo --------------------------------------------------------
def _distancia_manhattan(a, b):
    """Distancia simple entre puntos (x, y) — no hace falta haversine real
    para probar que la heurística visita, en cada paso, lo más cercano."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def test_vecino_mas_cercano_visita_en_orden_de_cercania():
    origen = (0, 0)
    # B está más cerca del origen que A o C; A está más cerca de B que C.
    paradas = [(10, 10), (1, 1), (5, 5)]  # A, B, C
    orden = rules.ordenar_vecino_mas_cercano(origen, paradas, _distancia_manhattan)
    # Desde (0,0): la más cercana es B (índice 1, dist=2), luego desde B la
    # más cercana entre las que quedan es C (índice 2, dist=8), luego A.
    assert orden == [1, 2, 0]


def test_vecino_mas_cercano_con_una_sola_parada():
    assert rules.ordenar_vecino_mas_cercano((0, 0), [(3, 4)], _distancia_manhattan) == [0]


def test_vecino_mas_cercano_sin_paradas():
    assert rules.ordenar_vecino_mas_cercano((0, 0), [], _distancia_manhattan) == []


def test_eta_por_parada_acumula_los_tramos():
    salida = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
    etas = rules.eta_por_parada(salida, [300, 600, 0])
    assert etas == [
        datetime(2026, 9, 9, 12, 5, tzinfo=UTC),
        datetime(2026, 9, 9, 12, 15, tzinfo=UTC),
        datetime(2026, 9, 9, 12, 15, tzinfo=UTC),
    ]


def test_duracion_heuristica_a_mas_velocidad_menos_tiempo():
    lenta = rules.duracion_heuristica_seg(10_000, Decimal("10"))
    rapida = rules.duracion_heuristica_seg(10_000, Decimal("30"))
    assert lenta > rapida > 0


def test_duracion_heuristica_sin_velocidad_no_revienta():
    assert rules.duracion_heuristica_seg(10_000, Decimal("0")) == 0
