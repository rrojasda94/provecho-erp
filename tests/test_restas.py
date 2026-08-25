"""Restas de una línea de venta: "sin cebolla" (RN-PRD-004, ADR-035).

El último tramo del orden de modificadores —tamaño → combinación → extras →
**restas**— era el único sin implementar. Lo que se prueba acá es lo que
puede salir mal en producción: que la resta se guarde con la línea, que solo
admita lo que la receta pone, que deje de descontar ese insumo del almacén,
que la reposición devuelva exactamente lo mismo que se consumió, y que
cocina lo vea.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.inventory.application.listeners import _consumos_de_items
from src.modules.inventory.application.queries_publicas import insumos_de_receta
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Categoria,
    CategoriaUdm,
    Receta,
    RecetaItem,
    UnidadMedida,
)
from src.modules.sales.application import catalogo as catalogo_uc
from src.modules.sales.application import kds as kds_uc
from src.modules.sales.application import ventas as ventas_uc
from src.modules.sales.application.errors import NoEncontrado, ReglaNegocio
from src.modules.sales.infrastructure.models import ProductoComercial, PuntoVenta
from src.modules.sales.infrastructure.repositories import (
    ProductoComercialRepo,
    VentaRepo,
)
from src.modules.users.infrastructure.models import (
    Empresa,
    Grupo,
    Marca,
    Persona,
    Sucursal,
    Usuario,
)

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

INSUMOS = ("Masa", "Queso", "Cebolla")


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def base(session):
    """Una pizza de tres insumos, que es lo mínimo para que quitar uno se
    distinga de quitarlos todos."""
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
    cat_udm = CategoriaUdm(nombre="Unidades")
    session.add_all([sucursal, cat_udm])
    session.flush()
    unidad = UnidadMedida(
        categoria_udm_id=cat_udm.id, nombre="Unidad", ratio=Decimal(1)
    )
    session.add(unidad)
    session.flush()
    categoria = Categoria(empresa_id=empresa.id, nombre="Mercadería")
    session.add(categoria)
    session.flush()

    articulos = {}
    for i, nombre in enumerate(INSUMOS, start=1):
        art = Articulo(
            empresa_id=empresa.id,
            id_interno=f"A{i:03d}",
            nombre=nombre,
            categoria_id=categoria.id,
            unidad_medida_id=unidad.id,
            tipo="mercaderia",
            costo_promedio=Decimal(2),
        )
        session.add(art)
        articulos[nombre] = art
    session.flush()

    receta = Receta(
        empresa_id=empresa.id,
        nombre="Pizza",
        rendimiento_cantidad=Decimal(1),
        rendimiento_unidad_medida_id=unidad.id,
    )
    session.add(receta)
    session.flush()
    for nombre in INSUMOS:
        session.add(
            RecetaItem(
                receta_id=receta.id,
                articulo_id=articulos[nombre].id,
                cantidad=Decimal(1),
            )
        )

    producto = ProductoComercial(
        id_interno="P001", marca_id=marca.id, nombre="Pizza", receta_id=receta.id
    )
    # Un artículo de otra receta: sirve para probar que no se puede quitar lo
    # que el plato nunca tuvo.
    ajeno = Articulo(
        empresa_id=empresa.id,
        id_interno="A999",
        nombre="Palta",
        categoria_id=categoria.id,
        unidad_medida_id=unidad.id,
        tipo="mercaderia",
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
    session.add_all([producto, ajeno, punto_venta, persona])
    session.flush()
    usuario = Usuario(
        username="ana.cajera", pin_hash="fake", persona_id=persona.id, tipo="humano"
    )
    session.add(usuario)
    session.flush()

    return {
        "empresa": empresa,
        "sucursal": sucursal,
        "producto": producto,
        "receta": receta,
        "articulos": articulos,
        "ajeno": ajeno,
        "punto_venta": punto_venta,
        "usuario": usuario,
    }


def _crear(session, base, *, sin=(), cantidad=1):
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
                "precio_unitario": Decimal("40.00"),
                "sin_articulo_ids": [str(a) for a in sin],
            }
        ],
    )


# --- Guardado y validación ---------------------------------------------------
def test_la_resta_se_guarda_con_la_linea(session, base):
    cebolla = base["articulos"]["Cebolla"].id
    venta = _crear(session, base, sin=[cebolla])
    session.flush()

    fila = VentaRepo(session).items(venta.id)[0]
    assert fila.sin_articulo_ids == [str(cebolla)]


def test_una_linea_sin_restas_no_guarda_lista_vacia(session, base):
    """NULL y no `[]`: "no quitó nada" es la ausencia del dato, no un dato.
    Es lo que vale además para todo lo vendido antes de esta migración."""
    venta = _crear(session, base)
    session.flush()
    assert VentaRepo(session).items(venta.id)[0].sin_articulo_ids is None


def test_no_se_puede_quitar_lo_que_la_receta_no_pone(session, base):
    with pytest.raises(ReglaNegocio, match="solo se puede quitar"):
        _crear(session, base, sin=[base["ajeno"].id])


def test_la_misma_resta_repetida_se_guarda_una_vez(session, base):
    cebolla = base["articulos"]["Cebolla"].id
    venta = _crear(session, base, sin=[cebolla, cebolla])
    session.flush()
    assert VentaRepo(session).items(venta.id)[0].sin_articulo_ids == [str(cebolla)]


def test_el_replay_del_hub_no_revalida_las_restas(session, base):
    """La venta ya se preparó y se cobró durante el corte; la receta pudo
    cambiar mientras tanto. Rechazarla ahora perdería una venta real
    (ADR-009), igual que con los grupos obligatorios."""
    filas, _, detalle = ventas_uc._armar_lineas(
        session,
        [
            {
                "producto_comercial_id": base["producto"].id,
                "cantidad": Decimal(1),
                "precio_unitario": Decimal("40.00"),
                "sin_articulo_ids": [str(base["ajeno"].id)],
            }
        ],
        sucursal_id=base["sucursal"].id,
        canal="pdv",
        modalidad="mesa",
        dia=None,
        exigir_opciones=False,
    )
    assert filas[0].sin_articulo_ids == [str(base["ajeno"].id)]
    assert detalle[0]["sin_articulo_ids"] == [str(base["ajeno"].id)]


# --- Consumo de inventario ---------------------------------------------------
def test_el_insumo_quitado_no_se_descuenta(session, base):
    cebolla = base["articulos"]["Cebolla"].id
    consumos = _consumos_de_items(
        session,
        [
            {
                "receta_id": str(base["receta"].id),
                "cantidad": "2",
                "sin_articulo_ids": [str(cebolla)],
            }
        ],
    )
    consumidos = {articulo_id for articulo_id, _ in consumos}
    assert cebolla not in consumidos
    assert len(consumos) == 2, "los otros dos insumos sí se descuentan"
    assert all(cantidad == Decimal(2) for _, cantidad in consumos)


def test_sin_restas_se_descuenta_la_receta_entera(session, base):
    """Compatibilidad: un payload sin el campo —los que ya están en vuelo—
    tiene que comportarse exactamente como antes."""
    consumos = _consumos_de_items(
        session, [{"receta_id": str(base["receta"].id), "cantidad": "1"}]
    )
    assert len(consumos) == len(INSUMOS)


def test_anular_repone_solo_lo_que_se_consumio(session, base, monkeypatch):
    """Lo que la línea no llevó tampoco vuelve al almacén: reponerlo dejaría
    stock que nunca salió y el conteo lo encontraría de más."""
    cebolla = base["articulos"]["Cebolla"].id
    venta = _crear(session, base, sin=[cebolla])
    session.flush()

    publicados = []
    # `monkeypatch` y no una asignación suelta: sin restaurar, el bus queda
    # mudo para el resto del archivo y las pruebas siguientes pasan por la
    # razón equivocada.
    monkeypatch.setattr(
        ventas_uc.event_bus,
        "publish",
        lambda evento, payload, session=None: publicados.append((evento, payload)),
    )
    ventas_uc.anular_venta(session, venta.id, base["usuario"].id)

    evento, payload = publicados[-1]
    assert evento == "sales.venta_anulada"
    assert payload["items"][0]["sin_articulo_ids"] == [str(cebolla)]


# --- Lo que ve cocina --------------------------------------------------------
def test_la_comanda_imprime_sin_cebolla(session, base):
    venta = _crear(session, base, sin=[base["articulos"]["Cebolla"].id])
    session.flush()
    texto = kds_uc.comanda(session, venta.id)["texto"]
    assert "SIN CEBOLLA" in texto


def test_el_avance_del_pedido_lista_las_restas(session, base):
    venta = _crear(session, base, sin=[base["articulos"]["Queso"].id])
    session.flush()
    item = kds_uc.avance_venta(session, venta.id)["items"][0]
    assert item["sin"] == ["Queso"]


# --- Qué se puede quitar -----------------------------------------------------
def test_los_quitables_son_los_insumos_de_la_receta(session, base):
    quitables = catalogo_uc.quitables_de(session, base["producto"].id)
    assert sorted(q["nombre"] for q in quitables) == sorted(INSUMOS)


def test_un_producto_sin_receta_no_ofrece_restas(session, base):
    """El padre de un grupo de variantes no se prepara: lo quitable sale de
    la variante elegida (RN-COM-022)."""
    padre = ProductoComercial(
        id_interno="P002",
        marca_id=base["producto"].marca_id,
        nombre="Pizza Familia",
        receta_id=None,
    )
    session.add(padre)
    session.flush()
    assert catalogo_uc.quitables_de(session, padre.id) == []


def test_insumos_de_receta_devuelve_id_y_nombre(session, base):
    insumos = insumos_de_receta(session, base["receta"].id)
    assert {i["nombre"] for i in insumos} == set(INSUMOS)
    assert all(i["articulo_id"] for i in insumos)


def test_insumos_de_receta_no_repite_insumo_con_lineas_condicionadas(session, base):
    """MitadXMitad (ADR-056): el mismo insumo aparece en una línea por cada
    mitad ("aplica_valores" distinto). "Sin cebolla" tiene que salir una sola
    vez, no una por cada línea condicionada que lo usa."""
    cebolla = base["articulos"]["Cebolla"]
    session.add(
        RecetaItem(
            receta_id=base["receta"].id,
            articulo_id=cebolla.id,
            cantidad=Decimal(1),
            aplica_valores=["valor-mitad-izquierda"],
        )
    )
    session.add(
        RecetaItem(
            receta_id=base["receta"].id,
            articulo_id=cebolla.id,
            cantidad=Decimal(1),
            aplica_valores=["valor-mitad-derecha"],
        )
    )
    session.flush()

    insumos = insumos_de_receta(session, base["receta"].id)
    nombres = [i["nombre"] for i in insumos]
    assert nombres.count("Cebolla") == 1


# --- Estructura: quitar extras y borrar grupos (deuda de ADR-023) ------------
def _extra(session, base, nombre, id_interno):
    extra = ProductoComercial(
        id_interno=id_interno,
        marca_id=base["producto"].marca_id,
        nombre=nombre,
        receta_id=base["receta"].id,
        es_extra=True,
    )
    session.add(extra)
    session.flush()
    return extra


def test_desvincular_extra_no_borra_el_extra(session, base):
    extra = _extra(session, base, "Extra Queso", "E001")
    catalogo_uc.vincular_extra(
        session, producto_id=base["producto"].id, extra_id=extra.id
    )
    catalogo_uc.desvincular_extra(
        session, producto_id=base["producto"].id, extra_id=extra.id
    )

    repo = ProductoComercialRepo(session)
    assert repo.admite_extra(base["producto"].id, extra.id) is None
    assert repo.get(extra.id) is not None, "el extra es un producto y sigue existiendo"


def test_desvincular_un_extra_que_no_estaba_es_404(session, base):
    extra = _extra(session, base, "Extra Aceituna", "E002")
    with pytest.raises(NoEncontrado):
        catalogo_uc.desvincular_extra(
            session, producto_id=base["producto"].id, extra_id=extra.id
        )


def test_borrar_grupo_suelta_sus_extras(session, base):
    """Borrar el grupo no puede llevarse los extras: son productos con su
    receta y su precio. Quedan ofreciéndose, ya sin mínimo obligatorio."""
    extra = _extra(session, base, "Salsa Ajo", "E003")
    grupo = catalogo_uc.crear_grupo_opcion(
        session, producto_id=base["producto"].id, nombre="Salsas", minimo=1
    )
    catalogo_uc.vincular_extra(
        session,
        producto_id=base["producto"].id,
        extra_id=extra.id,
        grupo_id=grupo.id,
    )

    catalogo_uc.borrar_grupo_opcion(
        session, producto_id=base["producto"].id, grupo_id=grupo.id
    )

    repo = ProductoComercialRepo(session)
    assert repo.grupos_de(base["producto"].id) == []
    vinculo = repo.admite_extra(base["producto"].id, extra.id)
    assert vinculo is not None and vinculo.grupo_id is None


def test_no_se_puede_borrar_el_grupo_de_otro_producto(session, base):
    otro = ProductoComercial(
        id_interno="P003",
        marca_id=base["producto"].marca_id,
        nombre="Lasaña",
        receta_id=base["receta"].id,
    )
    session.add(otro)
    session.flush()
    grupo = catalogo_uc.crear_grupo_opcion(
        session, producto_id=base["producto"].id, nombre="Salsas", minimo=1
    )
    with pytest.raises(NoEncontrado):
        catalogo_uc.borrar_grupo_opcion(
            session, producto_id=otro.id, grupo_id=grupo.id
        )
