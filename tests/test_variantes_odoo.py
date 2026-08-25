"""Atributos, variantes y recetas condicionadas de punta a punta (ADR-055/056).

Las funciones puras están en `test_receta_condicionada.py`. Acá se prueba lo
que solo se rompe con la base delante: que la condición viaje desde la venta
hasta el movimiento de inventario, que la unidad de la línea se convierta, y
que no se pueda elegir un valor que el producto no ofrece.

El caso de prueba es el archivo real de Charlie's reducido a lo mínimo que
distingue los comportamientos: una pizza mitad-y-mitad con tres sabores por
mitad. Con dos sabores no se distingue "coincide una mitad" de "coinciden las
dos"; con tres, sí.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.inventory.application import catalogo as inventario_uc
from src.modules.inventory.application import recetas as recetas_uc
from src.modules.inventory.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.inventory.application.listeners import _consumos_de_items
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Categoria,
    CategoriaUdm,
    Receta,
    RecetaItem,
    UnidadMedida,
)
from src.modules.sales.application import catalogo as valores_uc
from src.modules.sales.application import precios as precios_uc
from src.modules.sales.application import ventas as ventas_uc
from src.modules.sales.application.catalogo import valores_ofrecidos
from src.modules.sales.application.errors import ReglaNegocio as ReglaVenta
from src.modules.sales.infrastructure.models import (
    Atributo,
    AtributoValor,
    ProductoAtributoLinea,
    ProductoAtributoValor,
    ProductoComercial,
    ProductoExclusion,
    ProductoVarianteValor,
    PuntoVenta,
)
from src.modules.sales.infrastructure.repositories import VentaRepo
from src.modules.users.infrastructure.models import (
    Empresa,
    Grupo,
    Marca,
    Persona,
    Sucursal,
    Usuario,
)

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

SABORES = ("Americana", "Hawaiana", "Peperoni")


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
    marca = Marca(grupo_id=grupo.id, nombre="Charlie's Pizzas", tipo="restaurante")
    session.add_all([empresa, marca])
    session.flush()
    sucursal = Sucursal(
        marca_id=marca.id,
        empresa_id=empresa.id,
        nombre="Charlie's - Plaza",
        direccion="Jr. Ejemplo 123",
        tenencia="propia",
    )
    # Dos categorías de UdM: la de peso, donde "kg" y "g" conviven y se
    # convierten; y la de unidades sueltas, que no admite decimales.
    cat_peso = CategoriaUdm(nombre="Peso")
    cat_unidad = CategoriaUdm(nombre="Unidades")
    session.add_all([sucursal, cat_peso, cat_unidad])
    session.flush()
    kg = UnidadMedida(
        categoria_udm_id=cat_peso.id, nombre="kg", ratio=Decimal(1), decimales=3
    )
    gramo = UnidadMedida(
        categoria_udm_id=cat_peso.id, nombre="g", ratio=Decimal("0.001"), decimales=0
    )
    unidad = UnidadMedida(
        categoria_udm_id=cat_unidad.id, nombre="Unidad", ratio=Decimal(1), decimales=0
    )
    session.add_all([kg, gramo, unidad])
    session.flush()
    categoria = Categoria(empresa_id=empresa.id, nombre="Mercadería")
    session.add(categoria)
    session.flush()

    # La masa se lleva por unidad; los ingredientes por kilo.
    masa = Articulo(
        empresa_id=empresa.id,
        id_interno="A001",
        nombre="Masa",
        categoria_id=categoria.id,
        unidad_medida_id=unidad.id,
        tipo="mercaderia",
        costo_promedio=Decimal(2),
    )
    session.add(masa)
    articulos = {"Masa": masa}
    for i, nombre in enumerate(("Jamón", "Piña", "Peperoni"), start=2):
        art = Articulo(
            empresa_id=empresa.id,
            id_interno=f"A{i:03d}",
            nombre=nombre,
            categoria_id=categoria.id,
            unidad_medida_id=kg.id,
            tipo="mercaderia",
            costo_promedio=Decimal(20),
        )
        session.add(art)
        articulos[nombre] = art
    session.flush()

    receta = Receta(
        empresa_id=empresa.id,
        nombre="Pizza MitadxMitad Familiar",
        rendimiento_cantidad=Decimal(1),
        rendimiento_unidad_medida_id=unidad.id,
        es_kit=True,
    )
    session.add(receta)
    session.flush()

    producto = ProductoComercial(
        id_interno="P001",
        marca_id=marca.id,
        nombre="Pizza MitadxMitad Familiar",
        receta_id=receta.id,
    )
    session.add(producto)
    session.flush()

    # Dos atributos, `nunca`: la combinación se resuelve al vender y no
    # materializa 3 x 3 filas de producto.
    valores: dict[str, uuid.UUID] = {}
    for mitad in ("Mitad 1", "Mitad 2"):
        atributo = Atributo(
            empresa_id=empresa.id,
            nombre=mitad,
            modo_variante="nunca",
            display="radio",
        )
        session.add(atributo)
        session.flush()
        linea = ProductoAtributoLinea(
            producto_comercial_id=producto.id, atributo_id=atributo.id
        )
        session.add(linea)
        session.flush()
        for sabor in SABORES:
            valor = AtributoValor(atributo_id=atributo.id, nombre=sabor)
            session.add(valor)
            session.flush()
            ptav = ProductoAtributoValor(
                linea_id=linea.id, atributo_valor_id=valor.id
            )
            session.add(ptav)
            session.flush()
            valores[f"{mitad}: {sabor}"] = ptav.id

    def v(*claves: str) -> list[str]:
        return [str(valores[c]) for c in claves]

    # La masa va siempre. El jamón, solo si las DOS mitades lo llevan
    # (Americana u Hawaiana): es la forma exacta del archivo de Odoo, un
    # atributo por grupo en la misma línea. La piña va por mitad, que es la
    # forma correcta. El peperoni se teclea en gramos aunque el artículo se
    # lleve en kilos.
    session.add_all(
        [
            RecetaItem(
                receta_id=receta.id,
                articulo_id=masa.id,
                cantidad=Decimal(1),
                orden=0,
            ),
            RecetaItem(
                receta_id=receta.id,
                articulo_id=articulos["Jamón"].id,
                cantidad=Decimal("0.025"),
                orden=1,
                aplica_valores=v(
                    "Mitad 1: Americana",
                    "Mitad 1: Hawaiana",
                    "Mitad 2: Americana",
                    "Mitad 2: Hawaiana",
                ),
            ),
            # La piña se modela **por mitad**: una línea por mitad, a media
            # cantidad. Es la forma correcta y la que el jamón de arriba NO
            # usa a propósito —el archivo de Odoo trae el jamón en una sola
            # línea con los dos atributos, y así se comporta—. Las dos
            # conviven para que la diferencia sea visible y comprobable.
            RecetaItem(
                receta_id=receta.id,
                articulo_id=articulos["Piña"].id,
                cantidad=Decimal("0.0215"),
                orden=2,
                aplica_valores=v("Mitad 1: Hawaiana"),
            ),
            RecetaItem(
                receta_id=receta.id,
                articulo_id=articulos["Piña"].id,
                cantidad=Decimal("0.0215"),
                orden=3,
                aplica_valores=v("Mitad 2: Hawaiana"),
            ),
            RecetaItem(
                receta_id=receta.id,
                articulo_id=articulos["Peperoni"].id,
                cantidad=Decimal("24"),
                unidad_medida_id=gramo.id,
                orden=4,
                aplica_valores=v("Mitad 1: Peperoni", "Mitad 2: Peperoni"),
            ),
        ]
    )
    punto_venta = PuntoVenta(
        sucursal_id=sucursal.id,
        canal="trabajador",
        serie_boleta="B001",
        serie_factura="F001",
        politica_pago="al_finalizar",
    )
    persona = Persona(
        nombres="Ana",
        apellidos="Cajera",
        tipo_documento="dni",
        numero_documento="10000001",
    )
    session.add_all([punto_venta, persona])
    session.flush()
    usuario = Usuario(
        username="ana.cajera", pin_hash="fake", persona_id=persona.id, tipo="humano"
    )
    session.add(usuario)
    session.flush()

    return {
        "empresa": empresa,
        "marca": marca,
        "sucursal": sucursal,
        "producto": producto,
        "receta": receta,
        "articulos": articulos,
        "valores": valores,
        "punto_venta": punto_venta,
        "usuario": usuario,
        "udm": {"kg": kg, "g": gramo, "unidad": unidad},
    }


def _consumos(session, base, *claves: str) -> dict[str, Decimal]:
    """Lo que el listener descontaría por vender una de estas pizzas."""
    items = [
        {
            "receta_id": str(base["receta"].id),
            "cantidad": "1",
            "valores_variante_ids": [str(base["valores"][c]) for c in claves],
        }
    ]
    por_nombre = {a.id: n for n, a in base["articulos"].items()}
    # Suma y no dict: dos líneas del mismo artículo son dos movimientos de
    # stock, y quedarse con el último escondería justo lo que se quiere ver.
    total: dict[str, Decimal] = {}
    for articulo_id, cantidad in _consumos_de_items(session, items):
        nombre = por_nombre[articulo_id]
        total[nombre] = total.get(nombre, Decimal(0)) + cantidad
    return total


def _vender(session, base, claves=(), cantidad=1):
    return ventas_uc.crear_venta(
        session,
        sucursal_id=base["sucursal"].id,
        punto_venta_id=base["punto_venta"].id,
        canal="pdv",
        modalidad="mesa",
        usuario_id=base["usuario"].id,
        idempotency_key=f"key-{uuid.uuid4()}",
        items=[
            {
                "producto_comercial_id": base["producto"].id,
                "cantidad": Decimal(cantidad),
                "precio_unitario": Decimal("45.00"),
                "valores_variante_ids": [str(base["valores"][c]) for c in claves],
            }
        ],
    )


# --- La condición decide qué sale del almacén -------------------------------


def test_la_linea_sin_condicion_sale_siempre(session, base):
    """La masa no depende del sabor. Es también el caso de toda receta
    anterior a la migración: sin condición, se comporta como antes."""
    for combinacion in (
        ("Mitad 1: Americana", "Mitad 2: Americana"),
        ("Mitad 1: Peperoni", "Mitad 2: Hawaiana"),
    ):
        assert _consumos(session, base, *combinacion)["Masa"] == Decimal(1)


def test_media_hawaiana_lleva_media_pina(session, base):
    """Modelada por mitad, media hawaiana descuenta media piña.

    Comparar con `test_una_sola_mitad_no_alcanza_para_el_jamon`: mismo
    motor, dato distinto. La diferencia entre las dos pruebas **es** la
    deuda anotada sobre mitad-y-mitad, y cómo se salda.
    """
    consumos = _consumos(session, base, "Mitad 1: Hawaiana", "Mitad 2: Americana")
    assert consumos["Piña"] == Decimal("0.0215")


def test_hawaiana_entera_lleva_piña_entera(session, base):
    consumos = _consumos(session, base, "Mitad 1: Hawaiana", "Mitad 2: Hawaiana")
    assert consumos["Piña"] == Decimal("0.0430")


def test_sin_hawaiana_no_hay_pina(session, base):
    consumos = _consumos(session, base, "Mitad 1: Americana", "Mitad 2: Peperoni")
    assert "Piña" not in consumos


def test_el_jamon_pide_las_dos_mitades(session, base):
    """Americana + Hawaiana: las dos están en el conjunto, sale jamón."""
    consumos = _consumos(session, base, "Mitad 1: Americana", "Mitad 2: Hawaiana")
    assert consumos["Jamón"] == Decimal("0.025")


def test_una_sola_mitad_no_alcanza_para_el_jamon(session, base):
    """Media americana + media peperoni NO descuenta jamón.

    Regla de Odoo 18 y comportamiento del archivo que Charlie's ya tiene
    cargado. Está anotado como deuda: la corrección es de datos, no de
    motor.
    """
    consumos = _consumos(session, base, "Mitad 1: Americana", "Mitad 2: Peperoni")
    assert "Jamón" not in consumos


def test_una_pizza_sin_eleccion_solo_lleva_lo_incondicional(session, base):
    """Vender sin elegir —una venta vieja replicada desde el hub— no
    dispara ninguna línea condicionada."""
    consumos = _consumos(session, base)
    assert set(consumos) == {"Masa"}


# --- La unidad de la línea se convierte (RN-UDM-005) ------------------------


def test_los_gramos_de_la_linea_salen_en_kilos_del_articulo(session, base):
    """24 g de peperoni sobre un artículo que se lleva en kg = 0.024 kg.

    Es el caso literal del archivo de Charlie's, y el que hoy obliga a
    teclear "0.024" y equivocarse de un cero.
    """
    consumos = _consumos(session, base, "Mitad 1: Peperoni", "Mitad 2: Peperoni")
    assert consumos["Peperoni"] == Decimal("0.024")


def test_la_conversion_escala_con_lo_vendido(session, base):
    items = [
        {
            "receta_id": str(base["receta"].id),
            "cantidad": "3",
            "valores_variante_ids": [
                str(base["valores"]["Mitad 1: Peperoni"]),
                str(base["valores"]["Mitad 2: Peperoni"]),
            ],
        }
    ]
    consumos = dict(_consumos_de_items(session, items))
    assert consumos[base["articulos"]["Peperoni"].id] == Decimal("0.072")


# --- Lo que el producto ofrece ----------------------------------------------


def test_valores_ofrecidos_son_los_del_producto(session, base):
    ofrecidos = valores_ofrecidos(session, base["producto"])
    assert len(ofrecidos) == 6
    assert str(base["valores"]["Mitad 1: Americana"]) in ofrecidos


def test_una_variante_hereda_los_valores_del_padre(session, base):
    """Misma regla que ADR-042 para grupos y extras: dónde quedó colgado el
    atributo no puede decidir si el PDV lo ofrece."""
    hija = ProductoComercial(
        id_interno="P002",
        marca_id=base["marca"].id,
        nombre="Pizza MitadxMitad Familiar - Grande",
        receta_id=base["receta"].id,
        producto_padre_id=base["producto"].id,
    )
    session.add(hija)
    session.flush()
    assert valores_ofrecidos(session, hija) == valores_ofrecidos(
        session, base["producto"]
    )


def test_un_valor_retirado_deja_de_ofrecerse(session, base):
    ptav = session.get(
        ProductoAtributoValor, base["valores"]["Mitad 1: Peperoni"]
    )
    ptav.activo = False
    session.flush()
    assert str(ptav.id) not in valores_ofrecidos(session, base["producto"])


# --- La venta -----------------------------------------------------------------


def test_la_eleccion_se_guarda_con_la_linea(session, base):
    venta = _vender(session, base, ("Mitad 1: Hawaiana", "Mitad 2: Americana"))
    session.flush()
    linea = VentaRepo(session).items(venta.id)[0]
    assert linea.valores_variante_ids == [
        str(base["valores"]["Mitad 1: Hawaiana"]),
        str(base["valores"]["Mitad 2: Americana"]),
    ]


def test_no_se_vende_sin_elegir_los_atributos_que_ofrece(session, base):
    """RN-COM-040. Antes esto pasaba en silencio y era el bug caro: la línea
    se cobraba, ninguna condición de la receta se activaba y **no se
    descontaba ningún insumo**. El faltante recién aparecía en el conteo del
    mes, cuando ya nadie podía atarlo a esta venta."""
    with pytest.raises(ReglaVenta, match="falta elegir"):
        _vender(session, base)


def test_el_replay_del_hub_sigue_aceptando_la_linea_sin_eleccion(session, base):
    """La columna en NULL es lo que vale para todo lo vendido antes de la
    migración, y para lo que entró por el hub durante un corte: esa venta ya
    se preparó y se cobró (ADR-009). Rechazarla ahora perdería una venta
    real."""
    venta = ventas_uc.crear_venta(
        session,
        sucursal_id=base["sucursal"].id,
        punto_venta_id=base["punto_venta"].id,
        canal="pdv",
        modalidad="mesa",
        usuario_id=base["usuario"].id,
        idempotency_key=f"key-{uuid.uuid4()}",
        # `numero_orden` es lo que marca el replay: la venta ya trae su
        # número porque se lo dio el hub durante el corte.
        numero_orden=1,
        fecha_orden=date.today(),
        items=[
            {
                "producto_comercial_id": base["producto"].id,
                "cantidad": Decimal(1),
                "precio_unitario": Decimal("45.00"),
            }
        ],
    )
    session.flush()
    assert VentaRepo(session).items(venta.id)[0].valores_variante_ids is None


def test_no_se_puede_elegir_un_valor_ajeno(session, base):
    """Un valor de otro producto no es inocuo: puede activar líneas de
    receta y mover stock que nadie pidió."""
    otro = Atributo(empresa_id=base["empresa"].id, nombre="Temperatura")
    session.add(otro)
    session.flush()
    with pytest.raises(ReglaVenta, match="no ofrece"):
        ventas_uc.crear_venta(
            session,
            sucursal_id=base["sucursal"].id,
            punto_venta_id=base["punto_venta"].id,
            canal="pdv",
            modalidad="mesa",
            usuario_id=base["usuario"].id,
            idempotency_key=f"key-{uuid.uuid4()}",
            items=[
                {
                    "producto_comercial_id": base["producto"].id,
                    "cantidad": Decimal(1),
                    "precio_unitario": Decimal("45.00"),
                    "valores_variante_ids": [str(uuid.uuid4())],
                }
            ],
        )


def test_el_replay_del_hub_no_revalida(session, base):
    """ADR-009: esa venta ya se preparó y se cobró; el catálogo pudo cambiar
    durante el corte. Rechazarla ahora perdería una venta real."""
    ajeno = str(uuid.uuid4())
    fila, detalle, _ = ventas_uc._armar_item(
        session,
        {
            "producto_comercial_id": base["producto"].id,
            "cantidad": Decimal(1),
            "precio_unitario": Decimal("45.00"),
            "valores_variante_ids": [ajeno],
        },
        productos=ventas_uc.ProductoComercialRepo(session),
        sucursal_id=base["sucursal"].id,
        canal="pdv",
        modalidad="mesa",
        dia=None,
        exigir_opciones=False,
    )
    assert fila.valores_variante_ids == [ajeno]
    assert detalle["valores_variante_ids"] == [ajeno]


def test_la_eleccion_viaja_en_el_detalle_del_evento(session, base):
    """Sin esto, inventory no puede saber qué líneas condicionadas aplican."""
    _, detalle, _ = ventas_uc._armar_item(
        session,
        {
            "producto_comercial_id": base["producto"].id,
            "cantidad": Decimal(1),
            "precio_unitario": Decimal("45.00"),
            "valores_variante_ids": [
                str(base["valores"]["Mitad 1: Hawaiana"]),
            ],
        },
        productos=ventas_uc.ProductoComercialRepo(session),
        sucursal_id=base["sucursal"].id,
        canal="pdv",
        modalidad="mesa",
        dia=None,
    )
    assert detalle["valores_variante_ids"] == [
        str(base["valores"]["Mitad 1: Hawaiana"])
    ]


# --- Las dos mitades tienen que ser distintas (RN-COM-038) --------------------


def _excluir(session, base, atributo_a, atributo_b, sabor):
    session.add(
        ProductoExclusion(
            producto_atributo_valor_id=base["valores"][f"{atributo_a}: {sabor}"],
            excluye_valor_id=base["valores"][f"{atributo_b}: {sabor}"],
        )
    )
    session.flush()


def test_no_se_puede_elegir_el_mismo_sabor_en_las_dos_mitades(session, base):
    """Media hawaiana y media hawaiana no es una mitad-y-mitad: es una
    hawaiana entera, que se vende como su propio producto con su propia
    receta y su propio precio."""
    _excluir(session, base, "Mitad 1", "Mitad 2", "Hawaiana")
    with pytest.raises(ReglaVenta, match="dos mitades distintas"):
        _vender(session, base, ("Mitad 1: Hawaiana", "Mitad 2: Hawaiana"))


def test_la_exclusion_se_guarda_una_vez_y_vale_en_los_dos_sentidos(session, base):
    """Guardar el par simétrico sería la misma verdad dos veces, y la primera
    en desincronizarse."""
    _excluir(session, base, "Mitad 1", "Mitad 2", "Americana")
    izquierda = str(base["valores"]["Mitad 1: Americana"])
    derecha = str(base["valores"]["Mitad 2: Americana"])
    assert valores_uc.combinacion_excluida(session, [izquierda, derecha])
    assert valores_uc.combinacion_excluida(session, [derecha, izquierda])


def test_dos_sabores_distintos_si_se_venden(session, base):
    _excluir(session, base, "Mitad 1", "Mitad 2", "Hawaiana")
    venta = _vender(session, base, ("Mitad 1: Hawaiana", "Mitad 2: Americana"))
    session.flush()
    assert VentaRepo(session).items(venta.id)[0].valores_variante_ids


def test_un_solo_valor_nunca_choca(session, base):
    """La consulta corta antes de ir a la base: no hay par que excluir."""
    assert valores_uc.combinacion_excluida(session, []) is None
    assert (
        valores_uc.combinacion_excluida(
            session, [str(base["valores"]["Mitad 1: Hawaiana"])]
        )
        is None
    )


def test_el_orden_de_las_mitades_no_cambia_lo_que_se_consume(session, base):
    """«A + B» y «B + A» son el mismo plato. Con las líneas condicionadas a
    **una** mitad cada una, la simetría sale del modelo y no de ordenar nada
    al guardar."""
    ida = _consumos(session, base, "Mitad 1: Hawaiana", "Mitad 2: Peperoni")
    vuelta = _consumos(session, base, "Mitad 1: Peperoni", "Mitad 2: Hawaiana")
    assert ida == vuelta


# --- Alta de línea de receta --------------------------------------------------


def test_el_mismo_insumo_dos_veces_con_condiciones_distintas(session, base):
    """Es el caso que hace posible la mitad-y-mitad: el salame va en una
    línea para unos sabores y en otra, con otro gramaje, para otros."""
    salame = base["articulos"]["Peperoni"]
    recetas_uc.agregar_item(
        session,
        base["receta"].id,
        articulo_id=salame.id,
        expresion="0.01",
        aplica_valores=[str(base["valores"]["Mitad 1: Americana"])],
    )
    recetas_uc.agregar_item(
        session,
        base["receta"].id,
        articulo_id=salame.id,
        expresion="0.02",
        aplica_valores=[str(base["valores"]["Mitad 1: Hawaiana"])],
    )
    session.flush()


def test_el_mismo_insumo_con_la_misma_condicion_se_rechaza(session, base):
    """Sigue siendo la línea duplicada de siempre. El orden en que se listan
    los valores no la hace distinta."""
    masa = base["articulos"]["Masa"]
    condicion = [
        str(base["valores"]["Mitad 1: Americana"]),
        str(base["valores"]["Mitad 2: Hawaiana"]),
    ]
    recetas_uc.agregar_item(
        session, base["receta"].id, articulo_id=masa.id, expresion="1",
        aplica_valores=condicion,
    )
    session.flush()
    with pytest.raises(Conflicto, match="esa misma condición"):
        recetas_uc.agregar_item(
            session, base["receta"].id, articulo_id=masa.id, expresion="2",
            aplica_valores=list(reversed(condicion)),
        )


def test_una_unidad_de_otra_categoria_se_rechaza(session, base):
    """RN-UDM-001. Una línea que dice "kilos" sobre un artículo que se lleva
    por unidad es un gramaje que nadie puede interpretar."""
    with pytest.raises(ReglaNegocio, match="otra categoría"):
        recetas_uc.agregar_item(
            session,
            base["receta"].id,
            articulo_id=base["articulos"]["Masa"].id,
            expresion="1",
            unidad_medida_id=base["udm"]["kg"].id,
        )


def test_la_cantidad_se_redondea_con_los_decimales_de_la_linea(session, base):
    """El artículo se lleva en kg (3 decimales) y la línea se teclea en
    gramos (0): 24.4 g son 24 g, no 24.4."""
    item = recetas_uc.agregar_item(
        session,
        base["receta"].id,
        articulo_id=base["articulos"]["Jamón"].id,
        expresion="24.4",
        unidad_medida_id=base["udm"]["g"].id,
    )
    assert item.cantidad == Decimal("24")
    assert item.unidad_medida_id == base["udm"]["g"].id


# --- Categorías en árbol ------------------------------------------------------


def test_una_categoria_cuelga_de_otra(session, base):
    madre = inventario_uc.crear_categoria(
        session, empresa_id=base["empresa"].id, nombre="Materia Prima"
    )
    session.flush()
    hija = inventario_uc.crear_categoria(
        session,
        empresa_id=base["empresa"].id,
        nombre="Procesados",
        padre_id=madre.id,
    )
    assert hija.padre_id == madre.id


def test_la_madre_tiene_que_ser_de_la_misma_empresa(session, base):
    """El 404 y no un 403: para esta empresa esa categoría no existe."""
    with pytest.raises(NoEncontrado):
        inventario_uc.crear_categoria(
            session,
            empresa_id=base["empresa"].id,
            nombre="Huérfana",
            padre_id=uuid.uuid4(),
        )


def test_la_cadena_de_categorias_tiene_tope(session, base):
    """Sin tope, un ciclo que se coló por otra vía cuelga el request."""
    anterior = None
    for i in range(inventario_uc.PROFUNDIDAD_MAXIMA_CATEGORIA + 1):
        anterior = inventario_uc.crear_categoria(
            session,
            empresa_id=base["empresa"].id,
            nombre=f"Nivel {i}",
            padre_id=anterior.id if anterior else None,
        )
        session.flush()
    with pytest.raises(ReglaNegocio, match="profunda"):
        inventario_uc.crear_categoria(
            session,
            empresa_id=base["empresa"].id,
            nombre="Una de más",
            padre_id=anterior.id,
        )


# --- La variante materializada ------------------------------------------------


def test_una_variante_sabe_que_combinacion_es(session, base):
    """`producto_variante_valor` es lo que convierte una fila hija en una
    combinación: sin ella, "Pizza Familiar" es solo un nombre."""
    hija = ProductoComercial(
        id_interno="P003",
        marca_id=base["marca"].id,
        nombre="Pizza Americana/Hawaiana",
        receta_id=base["receta"].id,
        producto_padre_id=base["producto"].id,
    )
    session.add(hija)
    session.flush()
    for clave in ("Mitad 1: Americana", "Mitad 2: Hawaiana"):
        session.add(
            ProductoVarianteValor(
                producto_comercial_id=hija.id,
                producto_atributo_valor_id=base["valores"][clave],
            )
        )
    session.flush()
    combinacion = {
        str(v.producto_atributo_valor_id)
        for v in session.query(ProductoVarianteValor).filter_by(
            producto_comercial_id=hija.id
        )
    }
    assert combinacion == {
        str(base["valores"]["Mitad 1: Americana"]),
        str(base["valores"]["Mitad 2: Hawaiana"]),
    }


# --- Lo que la carta le ofrece al PDV (RN-COM-040) -----------------------------
def _ofrecidos(session, base):
    return valores_uc.atributos_ofrecidos(session, [base["producto"]])[
        base["producto"].id
    ]


def test_la_carta_ofrece_los_atributos_del_producto(session, base):
    """El bug de origen: la carta solo leía `producto_opcion_grupo` —vacío en
    el catálogo real— así que el configurador del PDV no mostraba ninguna
    opción y la pizza se podía cobrar sin sabores."""
    ofrecidos = _ofrecidos(session, base)

    assert [a["nombre"] for a in ofrecidos] == ["Mitad 1", "Mitad 2"]
    assert {v["nombre"] for v in ofrecidos[0]["valores"]} == set(SABORES)


def test_la_carta_no_ofrece_un_valor_retirado(session, base):
    """Hermano del de `valores_ofrecidos`, pero del lado de la carta: son dos
    consumidores del mismo criterio y tienen que coincidir, porque lo que la
    pantalla ofrece es lo que el servidor va a exigir."""
    ptav = session.get(ProductoAtributoValor, base["valores"]["Mitad 1: Peperoni"])
    ptav.activo = False
    session.flush()

    ofrecidos = _ofrecidos(session, base)

    assert "Peperoni" not in {v["nombre"] for v in ofrecidos[0]["valores"]}
    assert "Peperoni" in {v["nombre"] for v in ofrecidos[1]["valores"]}


def test_un_atributo_siempre_no_se_pregunta(session, base):
    """`modo_variante='siempre'` ya se materializó como variantes: volver a
    preguntarlo sería pedir dos veces la misma elección."""
    session.query(Atributo).filter_by(nombre="Mitad 1").one().modo_variante = "siempre"
    session.flush()

    assert [a["nombre"] for a in _ofrecidos(session, base)] == ["Mitad 2"]


def test_la_variante_hereda_los_atributos_del_padre(session, base):
    """Dónde quedó colgado el atributo no puede decidir nada (ADR-042): el
    que arma una persona cuelga del padre, el que genera el importador cuelga
    de la variante."""
    hija = ProductoComercial(
        id_interno="P010",
        marca_id=base["marca"].id,
        nombre="Pizza MitadxMitad Familiar (Gruesa)",
        receta_id=base["receta"].id,
        producto_padre_id=base["producto"].id,
    )
    session.add(hija)
    session.flush()

    ofrecidos = valores_uc.atributos_ofrecidos(session, [hija])[hija.id]

    assert [a["nombre"] for a in ofrecidos] == ["Mitad 1", "Mitad 2"]


def test_las_exclusiones_viajan_y_valen_en_los_dos_sentidos(session, base):
    """La fila se guarda una vez: quien la dibuje tiene que comparar en ambas
    direcciones o la mitad de las pastillas quedaría habilitada."""
    izquierda = base["valores"]["Mitad 1: Peperoni"]
    derecha = base["valores"]["Mitad 2: Peperoni"]
    session.add(
        ProductoExclusion(
            producto_atributo_valor_id=izquierda, excluye_valor_id=derecha
        )
    )
    session.flush()

    pares = valores_uc.exclusiones_entre(session, [izquierda, derecha])

    assert pares == [(izquierda, derecha)]


def test_el_precio_extra_del_valor_se_cobra(session, base):
    """RN-COM-036 lo prometía en cuatro lugares y nada lo sumaba: era una
    columna editable desde la ficha que no cobraba."""
    ptav = session.get(ProductoAtributoValor, base["valores"]["Mitad 1: Peperoni"])
    ptav.precio_extra = Decimal("3.50")
    session.flush()

    recargo = precios_uc.recargo_de_valores(session, [str(ptav.id)])

    assert recargo == Decimal("3.50")
