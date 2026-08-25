"""`scripts/odoo/cargar_catalogo.py` avisa lo que salta por nombre repetido.

`Carga` inserta-o-salta por `Código`/`Nombre` y nunca actualiza (es una carga
de una sola vez, no un importador de correcciones). Antes de este cambio el
salto era mudo: correr la carga real sobre una base con datos de prueba
homónimos se veía **idéntica** a una carga limpia — nada distinguía "esto ya
estaba" de "esto se cargó ahora". Lo que se prueba acá es que correr la
misma carpeta dos veces cuenta y nombra lo que la segunda vez no toca.
"""

from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from scripts.odoo.cargar_catalogo import Carga
from src.core.database import Base
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
    session.add_all([empresa, marca])
    session.flush()
    return {"empresa": empresa, "marca": marca}


def _libro(ruta: Path, hojas: dict[str, list[dict]]) -> None:
    """Un `.xlsx` mínimo: una hoja por clave, cabecera = las llaves del
    primer dict. Es lo que `filas()` del script espera leer."""
    wb = Workbook()
    wb.remove(wb.active)
    for nombre_hoja, filas in hojas.items():
        ws = wb.create_sheet(nombre_hoja)
        cabecera = list(filas[0].keys())
        ws.append(cabecera)
        for fila in filas:
            ws.append([fila.get(c, "") for c in cabecera])
    wb.save(ruta)


@pytest.fixture
def origen(tmp_path) -> Path:
    """Un insumo y una categoría de UdM: lo mínimo que toca dos libros
    distintos (fundaciones, artículos) y dos formas de "ya existe" —por
    nombre y por código."""
    _libro(
        tmp_path / "1-fundaciones.xlsx",
        {
            "Categorías UdM": [{"Nombre": "Peso"}],
            "Unidades": [
                {"Nombre": "Kilo", "Categoría UdM": "Peso", "Ratio": "1", "Decimales": "3"}
            ],
            "Categorías": [{"Nombre": "Insumos", "Categoría madre": ""}],
        },
    )
    _libro(
        tmp_path / "2-articulos.xlsx",
        {
            "Artículos": [
                {
                    "Código": "I001",
                    "Nombre": "Harina",
                    "Unidad": "Kilo",
                    "Tipo": "insumo",
                    "Categoría": "Insumos",
                    "Costo promedio": "3.50",
                    "Ref. externa": "",
                }
            ]
        },
    )
    return tmp_path


def test_la_primera_corrida_no_omite_nada(session, base, origen):
    carga = Carga(session, origen, base["empresa"], base["marca"])
    carga.fundaciones()
    carga.articulos()

    assert carga.creado.get("categorías de UdM") == 1
    assert carga.creado.get("unidades de medida") == 1
    assert carga.creado.get("categorías") == 1
    assert carga.creado.get("artículos") == 1
    assert carga.omitidos == {}


def test_la_segunda_corrida_avisa_todo_lo_que_ya_existia(session, base, origen):
    primera = Carga(session, origen, base["empresa"], base["marca"])
    primera.fundaciones()
    primera.articulos()

    segunda = Carga(session, origen, base["empresa"], base["marca"])
    segunda.fundaciones()
    segunda.articulos()

    # Nada nuevo: todo lo que la primera corrida creó, la segunda lo saltea.
    assert segunda.creado == {}
    assert segunda.omitidos["categorías de UdM"] == ["Peso"]
    assert segunda.omitidos["unidades de medida"] == ["Kilo"]
    assert segunda.omitidos["categorías"] == ["Insumos"]
    assert segunda.omitidos["artículos"] == ["Harina"]


def test_un_dato_de_prueba_homonimo_tapa_la_fila_real_pero_ahora_se_ve(
    session, base, origen
):
    """El caso que motivó el arreglo: alguien ya tecleó "Harina" a mano
    (con otro costo, otra categoría) antes de correr la carga real. La fila
    de Odoo se salta igual que si ya hubiera entrado — pero ahora queda
    registrado en `omitidos`, no en silencio."""
    from src.modules.inventory.application import catalogo as inv_uc

    cat_udm = inv_uc.crear_categoria_udm(session, nombre="Peso")
    udm = inv_uc.crear_unidad_medida(
        session, categoria_udm_id=cat_udm.id, nombre="Kilo",
        ratio=Decimal(1), decimales=3,
    )
    inv_uc.crear_articulo(
        session, empresa_id=base["empresa"].id, id_interno="I001",
        nombre="Harina", unidad_medida_id=udm.id, tipo="insumo",
        costo_promedio=Decimal("99.99"),
    )
    session.flush()

    carga = Carga(session, origen, base["empresa"], base["marca"])
    carga.fundaciones()
    carga.articulos()

    assert carga.creado.get("artículos") is None
    assert carga.omitidos["artículos"] == ["Harina"]
