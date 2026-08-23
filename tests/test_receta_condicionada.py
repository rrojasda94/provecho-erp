"""La regla que decide si una línea de receta le toca a una combinación.

Es la pieza de la que cuelga todo el modelo nuevo (ADR-056) y la única cuyo
error mueve stock de verdad: una línea que aplica de más descuenta un insumo
que nunca salió de la cámara, y el faltante aparece en el conteo del mes sin
que nadie pueda explicarlo.

Los casos con nombre de pizza son los del archivo real de Charlie's
(`Lista de materiales MITADXMITAD.xlsx`), no ejemplos inventados.
"""

from decimal import Decimal

import pytest

from src.modules.inventory.domain.rules import (
    aplica_a_variante,
    consumo_de_linea,
    convertir_cantidad,
)
from src.modules.sales.domain.rules import (
    DISPLAYS_ATRIBUTO,
    MODOS_VARIANTE,
    combinaciones_a_generar,
)

# Dos atributos, cuatro valores. `mitad1`/`mitad2` son los atributos;
# `m1_ame` se lee "Mitad 1: Americana".
ATRIBUTO_DE = {
    "m1_ame": "mitad1",
    "m1_haw": "mitad1",
    "m1_pep": "mitad1",
    "m2_ame": "mitad2",
    "m2_haw": "mitad2",
    "m2_pep": "mitad2",
    "tam_fam": "tamano",
    "tam_per": "tamano",
}


# --- Sin condición: el comportamiento de todas las recetas de hoy -----------


@pytest.mark.parametrize("condicion", [None, [], ()])
def test_sin_condicion_la_linea_aplica_siempre(condicion):
    """La columna nace nullable justamente para esto: una receta anterior a
    la migración no cambia de comportamiento."""
    assert aplica_a_variante(condicion, None, ATRIBUTO_DE) is True
    assert aplica_a_variante(condicion, ["m1_ame"], ATRIBUTO_DE) is True


def test_con_condicion_y_sin_eleccion_no_aplica():
    """Vender sin elegir nada no puede disparar una línea condicionada: es
    el caso de una venta vieja replicada desde el hub, y descontar de más
    ahí es peor que no descontar."""
    assert aplica_a_variante(["m1_ame"], None, ATRIBUTO_DE) is False
    assert aplica_a_variante(["m1_ame"], [], ATRIBUTO_DE) is False


# --- Un solo atributo en la condición: O entre sus valores ------------------


def test_un_atributo_basta_un_valor():
    assert aplica_a_variante(["m1_ame", "m1_haw"], ["m1_haw"], ATRIBUTO_DE) is True


def test_un_atributo_valor_distinto_no_aplica():
    assert aplica_a_variante(["m1_ame", "m1_haw"], ["m1_pep"], ATRIBUTO_DE) is False


# --- Dos atributos: Y entre grupos. El caso Charlie's ----------------------


def test_jamon_aplica_cuando_las_dos_mitades_lo_llevan():
    """"Jamón picado" pide {Americana, Hawaiana} en las DOS mitades."""
    condicion = ["m1_ame", "m1_haw", "m2_ame", "m2_haw"]
    assert aplica_a_variante(condicion, ["m1_ame", "m2_haw"], ATRIBUTO_DE) is True


def test_jamon_no_aplica_con_una_sola_mitad():
    """Media americana + media peperoni NO descuenta el jamón.

    Es la regla de Odoo 18 (`_skip_for_no_variant`) y es lo que asume el
    archivo que Charlie's ya tiene cargado — por eso se implementa así y no
    "mejor". La corrección real es de datos (una línea por mitad, a media
    cantidad) y está anotada en Deuda técnica.
    """
    condicion = ["m1_ame", "m1_haw", "m2_ame", "m2_haw"]
    assert aplica_a_variante(condicion, ["m1_ame", "m2_pep"], ATRIBUTO_DE) is False


def test_valores_de_mas_en_la_eleccion_no_estorban():
    """El tamaño elegido no participa de una condición que no lo nombra."""
    condicion = ["m1_ame", "m2_ame"]
    elegidos = ["m1_ame", "m2_ame", "tam_fam"]
    assert aplica_a_variante(condicion, elegidos, ATRIBUTO_DE) is True


def test_condicion_de_un_atributo_ignora_los_otros_elegidos():
    assert aplica_a_variante(["tam_fam"], ["m1_pep", "tam_fam"], ATRIBUTO_DE) is True


# --- Valores huérfanos: la lectura conservadora ----------------------------


def test_valor_sin_atributo_conocido_forma_su_propio_grupo():
    """Si alguien borró el valor, la línea apunta a nada. Se exige el id
    exacto en vez de dejar pasar la línea: descontar un insumo que quizá no
    va descuadra el conteo en silencio."""
    assert aplica_a_variante(["fantasma"], ["m1_ame"], {}) is False
    assert aplica_a_variante(["fantasma"], ["fantasma"], {}) is True


def test_dos_huerfanos_se_exigen_los_dos():
    """No se juntan en un solo grupo: eso sería un O entre valores de
    atributos que nadie sabe si son el mismo."""
    assert aplica_a_variante(["a", "b"], ["a"], {}) is False
    assert aplica_a_variante(["a", "b"], ["a", "b"], {}) is True


# --- Conversión de unidad (RN-UDM-005) -------------------------------------


def test_convertir_de_mililitros_a_litros():
    """30 ml de aceite en una receta cuyo artículo se lleva en litros."""
    assert convertir_cantidad(
        Decimal("30"), Decimal("0.001"), Decimal("1")
    ) == Decimal("0.030")


def test_convertir_de_gramos_a_kilos():
    assert convertir_cantidad(
        Decimal("250"), Decimal("0.001"), Decimal("1")
    ) == Decimal("0.250")


def test_convertir_desde_un_empaque():
    """Doypack de 2 kg = ratio 2 sobre Kilo: 3 doypacks son 6 kg."""
    assert convertir_cantidad(Decimal("3"), Decimal("2"), Decimal("1")) == Decimal("6")


def test_misma_unidad_no_cambia_nada():
    assert convertir_cantidad(
        Decimal("1.234"), Decimal("1"), Decimal("1")
    ) == Decimal("1.234")


def test_no_se_redondea_aca():
    """Redondear acá y otra vez en quien llama es cómo un gramo se vuelve
    dos. El redondeo va una sola vez, con los decimales de la unidad de
    destino (RN-GER-010)."""
    resultado = convertir_cantidad(Decimal("1"), Decimal("1"), Decimal("3"))
    assert resultado != Decimal("0.333")
    assert str(resultado).startswith("0.3333")


def test_ratio_cero_es_un_error_de_datos():
    with pytest.raises(ValueError):
        convertir_cantidad(Decimal("1"), Decimal("1"), Decimal("0"))


# --- La cuenta que descuenta y la que costea son la misma -------------------


def test_consumo_sin_merma_ni_conversion_es_la_cantidad():
    assert consumo_de_linea(Decimal("0.250"), Decimal(0)) == Decimal("0.250")


def test_consumo_suma_la_merma():
    """La merma es insumo que entra y no llega al plato."""
    assert consumo_de_linea(Decimal("100"), Decimal("10")) == Decimal("110.0")


def test_consumo_convierte_despues_de_la_merma():
    """30 ml + 10 % de merma = 33 ml = 0.033 L."""
    resultado = consumo_de_linea(
        Decimal("30"), Decimal("10"), Decimal("0.001"), Decimal("1")
    )
    assert resultado == Decimal("0.0330")


def test_consumo_ignora_ratios_a_medias():
    """Con un solo ratio no se puede convertir: se devuelve sin convertir en
    vez de inventar el otro. Es el caso de una UdM borrada."""
    assert consumo_de_linea(
        Decimal("30"), Decimal(0), Decimal("0.001"), None
    ) == Decimal("30")


def test_consumo_es_la_misma_cuenta_que_el_costo():
    """`costo_linea` y el descuento de stock salen de esta función. La
    prueba existe para que separarlas rompa algo."""
    cantidad = consumo_de_linea(Decimal("2"), Decimal("50"))
    costo_promedio = Decimal("10")
    assert cantidad == Decimal("3.00")
    assert cantidad * costo_promedio == Decimal("30.00")


# --- Vocabulario -----------------------------------------------------------


def test_modos_de_variante_son_los_tres_de_odoo():
    assert MODOS_VARIANTE == {"siempre", "dinamica", "nunca"}


def test_solo_siempre_materializa_filas():
    assert combinaciones_a_generar("siempre") is True
    assert combinaciones_a_generar("dinamica") is False
    assert combinaciones_a_generar("nunca") is False


def test_displays_declarados():
    assert "pildoras" in DISPLAYS_ATRIBUTO
