"""CRUD de atributos y el árbol que alimenta al lienzo (ADR-055, ADR-058).

Lo que se prueba acá es lo que decide si el catálogo se puede mantener a mano:
que un atributo se declare una vez y lo usen muchos productos, que retirar un
valor no rompa las ventas que lo nombran, y que el lienzo traiga el árbol
entero en una llamada en vez de una por variante.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.inventory.application import recetas as recetas_uc
from src.modules.inventory.infrastructure.models import CategoriaUdm, UnidadMedida
from src.modules.sales.application import atributos as atributos_uc
from src.modules.sales.application import catalogo as catalogo_uc
from src.modules.sales.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.users.infrastructure.models import Empresa, Grupo, Marca

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


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
    cat_udm = CategoriaUdm(nombre="Unidades")
    session.add_all([empresa, marca, cat_udm])
    session.flush()
    unidad = UnidadMedida(
        categoria_udm_id=cat_udm.id, nombre="Unidad", ratio=Decimal(1), decimales=0
    )
    session.add(unidad)
    session.flush()
    receta = recetas_uc.crear_receta(
        session,
        empresa_id=empresa.id,
        nombre="Pizza Peperoni Personal",
        rendimiento_cantidad=Decimal(1),
        rendimiento_unidad_medida_id=unidad.id,
    )
    session.flush()
    producto = catalogo_uc.crear_producto(
        session,
        id_interno="P001",
        marca_id=marca.id,
        nombre="Pizza Peperoni",
        receta_id=receta.id,
    )
    session.flush()
    return {"empresa": empresa, "marca": marca, "producto": producto, "receta": receta}


def _tamano(session, base, *valores):
    atributo = atributos_uc.crear_atributo(
        session, empresa_id=base["empresa"].id, nombre="Tamaño", display="pildoras"
    )
    for i, nombre in enumerate(valores):
        atributos_uc.agregar_valor(session, atributo.id, nombre=nombre, orden=i)
    session.flush()
    return atributo


# --- Atributos ----------------------------------------------------------------


def test_un_atributo_se_declara_una_vez(session, base):
    atributo = _tamano(session, base, "Personal", "Familiar")
    listados = atributos_uc.listar_atributos(session, base["empresa"].id)
    assert len(listados) == 1
    assert [v["nombre"] for v in listados[0]["valores"]] == ["Personal", "Familiar"]
    assert atributo.modo_variante == "nunca"


def test_no_se_repite_el_nombre_en_la_empresa(session, base):
    _tamano(session, base, "Personal")
    with pytest.raises(Conflicto, match="ya existe un atributo"):
        atributos_uc.crear_atributo(
            session, empresa_id=base["empresa"].id, nombre="Tamaño"
        )


def test_no_se_repite_el_valor_en_el_atributo(session, base):
    atributo = _tamano(session, base, "Personal")
    with pytest.raises(Conflicto, match="ya tiene el valor"):
        atributos_uc.agregar_valor(session, atributo.id, nombre="personal")


def test_el_vocabulario_se_valida(session, base):
    with pytest.raises(ReglaNegocio, match="modo de variante"):
        atributos_uc.crear_atributo(
            session, empresa_id=base["empresa"].id, nombre="X", modo_variante="a veces"
        )
    with pytest.raises(ReglaNegocio, match="forma de mostrar"):
        atributos_uc.crear_atributo(
            session, empresa_id=base["empresa"].id, nombre="Y", display="acordeon"
        )


def test_bajar_el_modo_no_borra_nada(session, base):
    """Alguien descubre que su atributo de 17 valores iba a materializar 289
    combinaciones y lo baja. Las que ya existen pueden estar en ventas."""
    atributo = _tamano(session, base, "Personal")
    atributos_uc.editar_atributo(session, atributo.id, modo_variante="siempre")
    atributos_uc.editar_atributo(session, atributo.id, modo_variante="nunca")
    assert atributo.modo_variante == "nunca"


# --- Lo que ofrece un producto ------------------------------------------------


def test_ofrecer_un_atributo_sin_lista_ofrece_todo(session, base):
    atributo = _tamano(session, base, "Personal", "Mediana", "Familiar")
    atributos_uc.ofrecer_atributo(
        session, producto_id=base["producto"].id, atributo_id=atributo.id
    )
    session.flush()
    arbol = catalogo_uc.arbol_de_producto(session, base["producto"].id)
    assert len(arbol["atributos"]) == 1
    assert len(arbol["atributos"][0]["valores"]) == 3


def test_ofrecerlo_dos_veces_no_duplica(session, base):
    """Volver a llamar agrega los que falten y no toca los que ya estaban."""
    atributo = _tamano(session, base, "Personal", "Mediana")
    atributos_uc.ofrecer_atributo(
        session, producto_id=base["producto"].id, atributo_id=atributo.id
    )
    atributos_uc.ofrecer_atributo(
        session, producto_id=base["producto"].id, atributo_id=atributo.id
    )
    session.flush()
    arbol = catalogo_uc.arbol_de_producto(session, base["producto"].id)
    assert len(arbol["atributos"]) == 1
    assert len(arbol["atributos"][0]["valores"]) == 2


def test_no_se_puede_ofrecer_un_valor_de_otro_atributo(session, base):
    atributo = _tamano(session, base, "Personal")
    with pytest.raises(ReglaNegocio, match="no tiene"):
        atributos_uc.ofrecer_atributo(
            session,
            producto_id=base["producto"].id,
            atributo_id=atributo.id,
            valores=[uuid.uuid4()],
        )


def test_el_precio_extra_vive_en_el_producto(session, base):
    """"Familiar" cuesta distinto en una pizza que en una lasaña: por eso el
    sobreprecio cuelga del PTAV y no del valor global."""
    atributo = _tamano(session, base, "Familiar")
    linea = atributos_uc.ofrecer_atributo(
        session, producto_id=base["producto"].id, atributo_id=atributo.id
    )
    session.flush()
    ptav = atributos_uc.ptav_de_linea(session, linea.id)[0]
    atributos_uc.fijar_precio_extra(session, ptav.id, precio_extra=Decimal("8.50"))
    session.flush()
    arbol = catalogo_uc.arbol_de_producto(session, base["producto"].id)
    assert arbol["atributos"][0]["valores"][0]["precio_extra"] == Decimal("8.50")


def test_el_precio_extra_no_es_negativo(session, base):
    atributo = _tamano(session, base, "Familiar")
    linea = atributos_uc.ofrecer_atributo(
        session, producto_id=base["producto"].id, atributo_id=atributo.id
    )
    session.flush()
    ptav = atributos_uc.ptav_de_linea(session, linea.id)[0]
    with pytest.raises(ReglaNegocio, match="negativo"):
        atributos_uc.fijar_precio_extra(session, ptav.id, precio_extra=Decimal(-1))


def test_retirar_un_valor_lo_desactiva_pero_no_lo_borra(session, base):
    """Las ventas viejas lo nombran y una comanda reimpresa tiene que seguir
    diciendo qué se preparó."""
    atributo = _tamano(session, base, "Personal", "Familiar")
    linea = atributos_uc.ofrecer_atributo(
        session, producto_id=base["producto"].id, atributo_id=atributo.id
    )
    session.flush()
    ptav = atributos_uc.ptav_de_linea(session, linea.id)[0]
    atributos_uc.retirar_valor(session, ptav.id)
    session.flush()
    arbol = catalogo_uc.arbol_de_producto(session, base["producto"].id)
    activos = [v for v in arbol["atributos"][0]["valores"] if v["activo"]]
    assert len(arbol["atributos"][0]["valores"]) == 2
    assert len(activos) == 1
    assert str(ptav.id) not in catalogo_uc.valores_ofrecidos(session, base["producto"])


# --- Exclusiones --------------------------------------------------------------


def test_un_valor_no_se_excluye_a_si_mismo(session, base):
    atributo = _tamano(session, base, "Personal")
    linea = atributos_uc.ofrecer_atributo(
        session, producto_id=base["producto"].id, atributo_id=atributo.id
    )
    session.flush()
    ptav = atributos_uc.ptav_de_linea(session, linea.id)[0]
    with pytest.raises(ReglaNegocio, match="a sí mismo"):
        atributos_uc.excluir(session, valor_id=ptav.id, excluye_id=ptav.id)


def test_la_exclusion_no_se_declara_dos_veces(session, base):
    atributo = _tamano(session, base, "Personal", "Familiar")
    linea = atributos_uc.ofrecer_atributo(
        session, producto_id=base["producto"].id, atributo_id=atributo.id
    )
    session.flush()
    a, b = atributos_uc.ptav_de_linea(session, linea.id)
    atributos_uc.excluir(session, valor_id=a.id, excluye_id=b.id)
    session.flush()
    # Al revés es el mismo par: se guarda una vez y se lee en los dos sentidos.
    with pytest.raises(Conflicto, match="ya están declarados"):
        atributos_uc.excluir(session, valor_id=b.id, excluye_id=a.id)


def test_se_puede_deshacer_una_exclusion(session, base):
    atributo = _tamano(session, base, "Personal", "Familiar")
    linea = atributos_uc.ofrecer_atributo(
        session, producto_id=base["producto"].id, atributo_id=atributo.id
    )
    session.flush()
    a, b = atributos_uc.ptav_de_linea(session, linea.id)
    atributos_uc.excluir(session, valor_id=a.id, excluye_id=b.id)
    session.flush()
    atributos_uc.dejar_de_excluir(session, valor_id=b.id, excluye_id=a.id)
    session.flush()
    assert catalogo_uc.combinacion_excluida(session, [str(a.id), str(b.id)]) is None
    with pytest.raises(NoEncontrado):
        atributos_uc.dejar_de_excluir(session, valor_id=a.id, excluye_id=b.id)


def test_el_arbol_trae_las_exclusiones(session, base):
    atributo = _tamano(session, base, "Personal", "Familiar")
    linea = atributos_uc.ofrecer_atributo(
        session, producto_id=base["producto"].id, atributo_id=atributo.id
    )
    session.flush()
    a, b = atributos_uc.ptav_de_linea(session, linea.id)
    atributos_uc.excluir(session, valor_id=a.id, excluye_id=b.id)
    session.flush()
    arbol = catalogo_uc.arbol_de_producto(session, base["producto"].id)
    assert arbol["exclusiones"] == [[str(a.id), str(b.id)]]


# --- El árbol -----------------------------------------------------------------


def test_el_arbol_incluye_lo_viejo(session, base):
    """Con el interruptor apagado el lienzo sigue dibujando grupos y extras:
    una sola forma de traer los datos evita que las dos pantallas se
    separen."""
    arbol = catalogo_uc.arbol_de_producto(session, base["producto"].id)
    assert "grupos" in arbol and "extras_sueltos" in arbol and "variantes" in arbol
    assert arbol["atributos"] == []
    assert arbol["exclusiones"] == []


def test_el_arbol_junta_los_atributos_del_padre_y_de_sus_variantes(session, base):
    """El lienzo dibuja el producto entero, así que necesita los atributos
    cuelguen de donde cuelguen (misma razón que ADR-042)."""
    # El padre agrupa y no se prepara (RN-COM-022): sin receta propia, que es
    # lo que `_validar_padre` exige antes de dejarle colgar variantes.
    padre = catalogo_uc.crear_producto(
        session,
        id_interno="P002",
        marca_id=base["marca"].id,
        nombre="Pizza Hawaiana",
    )
    session.flush()
    variante = catalogo_uc.crear_producto(
        session,
        id_interno="P003",
        marca_id=base["marca"].id,
        nombre="Pizza Hawaiana Familiar",
        receta_id=base["receta"].id,
        producto_padre_id=padre.id,
    )
    session.flush()
    del_padre = _tamano(session, base, "Personal", "Familiar")
    de_la_hija = atributos_uc.crear_atributo(
        session, empresa_id=base["empresa"].id, nombre="Temperatura"
    )
    atributos_uc.agregar_valor(session, de_la_hija.id, nombre="Caliente")
    session.flush()
    atributos_uc.ofrecer_atributo(
        session, producto_id=padre.id, atributo_id=del_padre.id
    )
    atributos_uc.ofrecer_atributo(
        session, producto_id=variante.id, atributo_id=de_la_hija.id
    )
    session.flush()
    arbol = catalogo_uc.arbol_de_producto(session, padre.id)
    assert {a["nombre"] for a in arbol["atributos"]} == {"Tamaño", "Temperatura"}


def test_un_producto_que_no_existe_no_devuelve_arbol(session, base):
    with pytest.raises(NoEncontrado):
        catalogo_uc.arbol_de_producto(session, uuid.uuid4())
