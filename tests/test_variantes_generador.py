"""El generador de combinaciones: los atributos `siempre` se vuelven filas.

Es lo último que faltaba de ADR-055 §3. Lo que se prueba acá es lo que decide
si el catálogo se puede regenerar sin miedo: que volver a apretar el botón no
duplique nada, que una combinación prohibida nunca se materialice, y que un
`id_interno` de cuatro caracteres no choque con los que ya existen.
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
from src.modules.sales.application import variantes as variantes_uc
from src.modules.sales.application.errors import Conflicto, ReglaNegocio
from src.modules.sales.infrastructure.models import (
    ProductoAtributoValor,
    ProductoComercial,
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
    # El padre nace **sin receta**: un producto con variantes no se prepara ni
    # se vende por sí mismo (RN-COM-022), y el generador lo exige igual que
    # `catalogo._validar_padre`.
    producto = catalogo_uc.crear_producto(
        session, id_interno="P001", marca_id=marca.id, nombre="Pizza Peperoni"
    )
    session.flush()
    return {
        "empresa": empresa,
        "marca": marca,
        "producto": producto,
        "unidad": unidad,
    }


def _atributo(session, base, nombre, *valores, modo="siempre"):
    atributo = atributos_uc.crear_atributo(
        session, empresa_id=base["empresa"].id, nombre=nombre, modo_variante=modo
    )
    for i, valor in enumerate(valores):
        atributos_uc.agregar_valor(session, atributo.id, nombre=valor, orden=i)
    session.flush()
    return atributo


def _ofrecer(session, base, atributo):
    atributos_uc.ofrecer_atributo(
        session, producto_id=base["producto"].id, atributo_id=atributo.id
    )
    session.flush()


def _ptav(session, base, nombre_valor) -> ProductoAtributoValor:
    """El PTAV del producto cuyo valor global se llama así."""
    for ptav in session.scalars(select_ptav(base["producto"].id)):
        valor = atributos_uc.exigir_valor(session, ptav.atributo_valor_id)
        if valor.nombre == nombre_valor:
            return ptav
    raise AssertionError(f"no hay PTAV para '{nombre_valor}'")


def select_ptav(producto_id):
    from sqlalchemy import select

    from src.modules.sales.infrastructure.models import ProductoAtributoLinea

    return (
        select(ProductoAtributoValor)
        .join(
            ProductoAtributoLinea,
            ProductoAtributoValor.linea_id == ProductoAtributoLinea.id,
        )
        .where(ProductoAtributoLinea.producto_comercial_id == producto_id)
    )


# --- El producto cartesiano ---------------------------------------------------


def test_dos_ejes_dan_el_producto_cartesiano(session, base):
    _ofrecer(session, base, _atributo(session, base, "Tamaño", "Personal", "Familiar"))
    _ofrecer(session, base, _atributo(session, base, "Masa", "Delgada", "Gruesa", "Rellena"))

    creadas = variantes_uc.generar_variantes(session, base["producto"].id)

    assert len(creadas) == 6
    assert all(v.producto_padre_id == base["producto"].id for v in creadas)


def test_el_nombre_lleva_los_valores_entre_parentesis(session, base):
    _ofrecer(session, base, _atributo(session, base, "Tamaño", "Familiar"))

    creadas = variantes_uc.generar_variantes(session, base["producto"].id)

    assert creadas[0].nombre == "Pizza Peperoni (Familiar)"


def test_la_variante_hereda_marca_categoria_y_empaque(session, base):
    padre = base["producto"]
    padre.modalidades_empaque = ["delivery"]
    _ofrecer(session, base, _atributo(session, base, "Tamaño", "Familiar"))

    hija = variantes_uc.generar_variantes(session, padre.id)[0]

    assert hija.marca_id == padre.marca_id
    assert hija.categoria_id == padre.categoria_id
    assert hija.empaque_id == padre.empaque_id
    assert hija.modalidades_empaque == ["delivery"]


def test_la_variante_nace_sin_receta(session, base):
    """No hay ninguna de dónde copiarla —el padre no puede tener— y exigirla
    haría imposible el generador. Queda como pendiente visible en la ficha."""
    _ofrecer(session, base, _atributo(session, base, "Tamaño", "Familiar"))

    hija = variantes_uc.generar_variantes(session, base["producto"].id)[0]

    assert hija.receta_id is None


# --- Idempotencia -------------------------------------------------------------


def test_volver_a_generar_no_crea_nada(session, base):
    _ofrecer(session, base, _atributo(session, base, "Tamaño", "Personal", "Familiar"))
    variantes_uc.generar_variantes(session, base["producto"].id)

    segunda = variantes_uc.generar_variantes(session, base["producto"].id)

    assert segunda == []


def test_agregar_un_valor_solo_genera_lo_que_falta(session, base):
    atributo = _atributo(session, base, "Tamaño", "Personal", "Familiar")
    _ofrecer(session, base, atributo)
    variantes_uc.generar_variantes(session, base["producto"].id)

    atributos_uc.agregar_valor(session, atributo.id, nombre="Mediana", orden=2)
    _ofrecer(session, base, atributo)
    creadas = variantes_uc.generar_variantes(session, base["producto"].id)

    assert len(creadas) == 1
    assert creadas[0].nombre == "Pizza Peperoni (Mediana)"


def test_una_variante_desactivada_sigue_ocupando_su_combinacion(session, base):
    """Regenerarla crearía una segunda fila para el mismo plato."""
    _ofrecer(session, base, _atributo(session, base, "Tamaño", "Familiar"))
    hija = variantes_uc.generar_variantes(session, base["producto"].id)[0]
    hija.activo = False
    session.flush()

    assert variantes_uc.generar_variantes(session, base["producto"].id) == []


# --- Exclusiones (RN-COM-038) -------------------------------------------------


def test_una_combinacion_excluida_no_se_materializa(session, base):
    _ofrecer(session, base, _atributo(session, base, "Mitad 1", "Americana", "Hawaiana"))
    _ofrecer(session, base, _atributo(session, base, "Mitad 2", "Americana", "Hawaiana"))
    # Las dos mitades tienen que ser distintas: se excluye cada sabor consigo
    # mismo del otro lado. Quedan 4 - 2 = 2 combinaciones.
    for sabor in ("Americana", "Hawaiana"):
        pares = [
            p
            for p in session.scalars(select_ptav(base["producto"].id))
            if atributos_uc.exigir_valor(session, p.atributo_valor_id).nombre == sabor
        ]
        atributos_uc.excluir(session, valor_id=pares[0].id, excluye_id=pares[1].id)
    session.flush()

    creadas = variantes_uc.generar_variantes(session, base["producto"].id)

    assert len(creadas) == 2
    for variante in creadas:
        assert "Americana, Hawaiana" in variante.nombre or (
            "Hawaiana, Americana" in variante.nombre
        )


# --- Qué eje entra ------------------------------------------------------------


@pytest.mark.parametrize("modo", ["nunca", "dinamica"])
def test_los_otros_modos_no_materializan(session, base, modo):
    """`nunca` es el caso de Mitad 1 x Mitad 2 —361 filas que no existen— y
    `dinamica` materializa al vender, que todavía no está construido."""
    _ofrecer(session, base, _atributo(session, base, "Tamaño", "Familiar", modo=modo))

    with pytest.raises(ReglaNegocio, match="ningún atributo"):
        variantes_uc.generar_variantes(session, base["producto"].id)


def test_solo_entra_el_eje_siempre_cuando_hay_de_los_dos(session, base):
    _ofrecer(session, base, _atributo(session, base, "Tamaño", "Personal", "Familiar"))
    _ofrecer(
        session,
        base,
        _atributo(session, base, "Mitad 1", "Americana", "Hawaiana", modo="nunca"),
    )

    creadas = variantes_uc.generar_variantes(session, base["producto"].id)

    assert len(creadas) == 2


def test_un_valor_retirado_no_entra_en_la_combinacion(session, base):
    _ofrecer(session, base, _atributo(session, base, "Tamaño", "Personal", "Familiar"))
    atributos_uc.retirar_valor(session, _ptav(session, base, "Personal").id)
    session.flush()

    creadas = variantes_uc.generar_variantes(session, base["producto"].id)

    assert [v.nombre for v in creadas] == ["Pizza Peperoni (Familiar)"]


# --- El código de cuatro caracteres -------------------------------------------


def test_el_codigo_no_choca_con_uno_existente(session, base):
    """`id_interno` es único en todo el grupo: el generador tiene que saltear
    los que ya están, no fallar contra el UNIQUE."""
    catalogo_uc.crear_producto(
        session, id_interno="P000", marca_id=base["marca"].id, nombre="Ocupado"
    )
    session.flush()
    _ofrecer(session, base, _atributo(session, base, "Tamaño", "Personal", "Familiar"))

    creadas = variantes_uc.generar_variantes(session, base["producto"].id)

    codigos = [v.id_interno for v in creadas]
    assert "P000" not in codigos
    assert len(set(codigos)) == len(codigos)
    assert all(len(c) == 4 for c in codigos)


def test_el_nombre_largo_se_recorta_a_150(session, base):
    """Postgres rechaza el INSERT y SQLite lo trunca en silencio: si no se
    recorta acá, la prueba pasa en verde y la generación revienta en producción.
    """
    base["producto"].nombre = "P" * 140
    _ofrecer(session, base, _atributo(session, base, "Tamaño", "Familiar Extra Grande"))

    hija = variantes_uc.generar_variantes(session, base["producto"].id)[0]

    assert len(hija.nombre) <= 150


# --- Guardas del padre (RN-COM-022) -------------------------------------------


def test_un_extra_no_admite_variantes(session, base):
    extra = catalogo_uc.crear_producto(
        session,
        id_interno="E001",
        marca_id=base["marca"].id,
        nombre="Queso Extra",
        es_extra=True,
    )
    session.flush()

    with pytest.raises(Conflicto, match="extra"):
        variantes_uc.generar_variantes(session, extra.id)


def test_un_producto_con_receta_propia_no_genera(session, base, ):
    receta = recetas_uc.crear_receta(
        session,
        empresa_id=base["empresa"].id,
        nombre="Pizza Peperoni",
        rendimiento_cantidad=Decimal(1),
        rendimiento_unidad_medida_id=base["unidad"].id,
    )
    session.flush()
    base["producto"].receta_id = receta.id
    _ofrecer(session, base, _atributo(session, base, "Tamaño", "Familiar"))

    with pytest.raises(Conflicto, match="receta propia"):
        variantes_uc.generar_variantes(session, base["producto"].id)


def test_una_variante_no_admite_variantes_propias(session, base):
    _ofrecer(session, base, _atributo(session, base, "Tamaño", "Familiar"))
    hija = variantes_uc.generar_variantes(session, base["producto"].id)[0]

    with pytest.raises(Conflicto, match="ya es una variante"):
        variantes_uc.generar_variantes(session, hija.id)


def test_un_producto_que_no_existe_no_genera(session, base):
    from src.modules.sales.application.errors import NoEncontrado

    with pytest.raises(NoEncontrado):
        variantes_uc.generar_variantes(session, uuid.uuid4())


# --- El aviso de precio -------------------------------------------------------


def test_la_variante_recien_generada_se_reporta_sin_precio(session, base):
    """`carta()` descarta en silencio lo que no sabe cobrar, así que sin este
    aviso alguien genera doce combinaciones y no ve ninguna en el PDV."""
    _ofrecer(session, base, _atributo(session, base, "Tamaño", "Personal", "Familiar"))
    creadas = variantes_uc.generar_variantes(session, base["producto"].id)

    faltan = variantes_uc.sin_precio(session, creadas)

    assert sorted(faltan) == [
        "Pizza Peperoni (Familiar)",
        "Pizza Peperoni (Personal)",
    ]


def test_sin_variantes_no_hay_nada_que_avisar(session, base):
    assert variantes_uc.sin_precio(session, []) == []


def test_las_variantes_generadas_son_hijas_consultables(session, base):
    from sqlalchemy import select

    _ofrecer(session, base, _atributo(session, base, "Tamaño", "Personal", "Familiar"))
    variantes_uc.generar_variantes(session, base["producto"].id)

    hijas = session.scalars(
        select(ProductoComercial).where(
            ProductoComercial.producto_padre_id == base["producto"].id
        )
    ).all()
    assert len(hijas) == 2
