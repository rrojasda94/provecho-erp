"""La matriz: el recetario como grilla, y el guardado por lote (ADR-057).

Lo que se prueba es lo que hace que pegar un rectángulo desde Excel sea
seguro: que la celda se identifique por `(receta, insumo, condición)` y no por
un id que la planilla no tiene, que vaciarla borre la línea, y que **una celda
mala no arrastre a las demás** — que es el modo de falla que hace que nadie
vuelva a pegar nada.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.inventory.application import matriz as matriz_uc
from src.modules.inventory.application import recetas as recetas_uc
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Categoria,
    CategoriaUdm,
    UnidadMedida,
)
from src.modules.users.infrastructure.models import Empresa, Grupo

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
    cat_peso = CategoriaUdm(nombre="Peso")
    session.add_all([empresa, cat_peso])
    session.flush()
    kg = UnidadMedida(
        categoria_udm_id=cat_peso.id, nombre="kg", ratio=Decimal(1), decimales=4
    )
    gramo = UnidadMedida(
        categoria_udm_id=cat_peso.id, nombre="g", ratio=Decimal("0.001"), decimales=0
    )
    session.add_all([kg, gramo])
    session.flush()
    categoria = Categoria(empresa_id=empresa.id, nombre="Mercadería")
    session.add(categoria)
    session.flush()

    articulos = {}
    for i, nombre in enumerate(("Queso", "Jamón", "Masa"), start=1):
        art = Articulo(
            empresa_id=empresa.id,
            id_interno=f"A{i:03d}",
            nombre=nombre,
            categoria_id=categoria.id,
            unidad_medida_id=kg.id,
            tipo="insumo",
            costo_promedio=Decimal(20),
        )
        session.add(art)
        articulos[nombre] = art
    session.flush()

    recetas = {}
    for nombre in ("Pizza Personal", "Pizza Familiar"):
        recetas[nombre] = recetas_uc.crear_receta(
            session,
            empresa_id=empresa.id,
            nombre=nombre,
            rendimiento_cantidad=Decimal(1),
            rendimiento_unidad_medida_id=kg.id,
        )
    session.flush()
    return {
        "empresa": empresa,
        "articulos": articulos,
        "recetas": recetas,
        "udm": {"kg": kg, "g": gramo},
    }


def _celda(base, receta, insumo, expresion, **extra):
    return {
        "receta_id": base["recetas"][receta].id,
        "articulo_id": base["articulos"][insumo].id,
        "expresion": expresion,
        **extra,
    }


def _guardar(session, base, celdas):
    return matriz_uc.guardar(
        session, empresa_id=base["empresa"].id, celdas=celdas
    )


def _grilla(session, base):
    return matriz_uc.grilla(session, empresa_id=base["empresa"].id)


# --- Guardar ------------------------------------------------------------------


def test_una_celda_nueva_crea_la_linea(session, base):
    r = _guardar(session, base, [_celda(base, "Pizza Personal", "Queso", "0.15")])
    assert r["aplicadas"] == 1 and r["con_problema"] == 0
    assert r["resultados"][0]["accion"] == "creada"
    assert r["resultados"][0]["cantidad"] == Decimal("0.15")


def test_la_misma_celda_dos_veces_actualiza(session, base):
    _guardar(session, base, [_celda(base, "Pizza Personal", "Queso", "0.15")])
    r = _guardar(session, base, [_celda(base, "Pizza Personal", "Queso", "0.2")])
    assert r["resultados"][0]["accion"] == "actualizada"
    celdas = _grilla(session, base)["celdas"]
    assert len(celdas) == 1
    assert celdas[0]["cantidad"] == Decimal("0.2")


def test_vaciar_la_celda_borra_la_linea(session, base):
    """En una grilla, vaciar la celda es cómo se dice "este insumo no va en
    esta receta". Pedir un botón aparte sería inventar un gesto."""
    _guardar(session, base, [_celda(base, "Pizza Personal", "Queso", "0.15")])
    r = _guardar(session, base, [_celda(base, "Pizza Personal", "Queso", "")])
    assert r["resultados"][0]["accion"] == "borrada"
    assert _grilla(session, base)["celdas"] == []


def test_vaciar_una_celda_que_ya_estaba_vacia_no_es_error(session, base):
    """Pegar un rectángulo con huecos no puede reportar cuarenta problemas."""
    r = _guardar(session, base, [_celda(base, "Pizza Personal", "Queso", "")])
    assert r["resultados"][0]["accion"] == "sin_cambio"
    assert r["con_problema"] == 0


def test_la_aritmetica_la_evalua_el_servidor(session, base):
    """RN-COM-024: el navegador manda la operación, nunca el resultado."""
    _guardar(session, base, [_celda(base, "Pizza Personal", "Queso", "450/3")])
    celda = _grilla(session, base)["celdas"][0]
    assert celda["cantidad"] == Decimal("150")
    assert celda["expresion"] == "450/3"


def test_la_unidad_de_la_linea_decide_el_redondeo(session, base):
    """Quien teclea gramos espera que 24.4 sea 24, no tres decimales de kilo."""
    _guardar(
        session,
        base,
        [
            _celda(
                base,
                "Pizza Personal",
                "Jamón",
                "24.4",
                unidad_medida_id=base["udm"]["g"].id,
            )
        ],
    )
    celda = _grilla(session, base)["celdas"][0]
    assert celda["cantidad"] == Decimal("24")
    assert celda["unidad"] == "g"


# --- Una celda mala no arrastra a las demás ------------------------------------


def test_una_celda_mala_no_tumba_el_lote(session, base):
    """El motivo entero de que cada celda vaya en su propio SAVEPOINT."""
    r = _guardar(
        session,
        base,
        [
            _celda(base, "Pizza Personal", "Queso", "0.15"),
            {
                "receta_id": base["recetas"]["Pizza Personal"].id,
                "articulo_id": uuid.uuid4(),
                "expresion": "1",
            },
            _celda(base, "Pizza Familiar", "Queso", "0.3"),
        ],
    )
    assert r["aplicadas"] == 2
    assert r["con_problema"] == 1
    assert len(_grilla(session, base)["celdas"]) == 2


def test_una_receta_de_otra_empresa_no_entra(session, base):
    r = _guardar(
        session,
        base,
        [
            {
                "receta_id": uuid.uuid4(),
                "articulo_id": base["articulos"]["Queso"].id,
                "expresion": "1",
            }
        ],
    )
    assert r["con_problema"] == 1
    assert "receta" in r["resultados"][0]["detalle"]


def test_hay_tope_de_celdas_por_guardado(session, base):
    muchas = [
        _celda(base, "Pizza Personal", "Queso", "1")
        for _ in range(matriz_uc.MAXIMO_CELDAS + 1)
    ]
    with pytest.raises(Exception, match="demasiadas celdas"):
        _guardar(session, base, muchas)


# --- La grilla ----------------------------------------------------------------


def test_la_grilla_solo_trae_los_insumos_que_se_usan(session, base):
    """Una grilla con las cuatrocientas filas del catálogo es una grilla
    vacía."""
    _guardar(session, base, [_celda(base, "Pizza Personal", "Queso", "0.15")])
    grilla = _grilla(session, base)
    assert [i["nombre"] for i in grilla["insumos"]] == ["Queso"]
    assert len(grilla["recetas"]) == 2


def test_la_grilla_vacia_no_revienta(session, base):
    grilla = _grilla(session, base)
    assert grilla["insumos"] == [] and grilla["celdas"] == []
    assert len(grilla["recetas"]) == 2


def test_se_puede_filtrar_por_receta(session, base):
    _guardar(
        session,
        base,
        [
            _celda(base, "Pizza Personal", "Queso", "0.15"),
            _celda(base, "Pizza Familiar", "Queso", "0.3"),
        ],
    )
    grilla = matriz_uc.grilla(
        session,
        empresa_id=base["empresa"].id,
        receta_ids=[base["recetas"]["Pizza Personal"].id],
    )
    assert len(grilla["recetas"]) == 1
    assert len(grilla["celdas"]) == 1
