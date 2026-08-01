"""Slice PDV (ADR-016): mesa tipada, cobro dividido por grupos, receptor
tecleado en caja y descuento manual de la orden.

Cada prueba cubre un hueco que el punto de venta necesitaba y el modelo no
daba. La compatibilidad hacia atrás tiene sus propias pruebas: nada de lo
agregado puede cambiar el comportamiento de una venta que no lo usa.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.core.events import event_bus
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Categoria,
    CategoriaUdm,
    Receta,
    RecetaItem,
    UnidadMedida,
)
from src.modules.sales.application import catalogo as catalogo_uc
from src.modules.sales.application import clientes as clientes_uc
from src.modules.sales.application import comprobantes as comprobantes_uc
from src.modules.sales.application import mesas as mesas_uc
from src.modules.sales.application import ventas as ventas_uc
from src.modules.sales.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import (
    MedioPago,
    ProductoComercial,
    PuntoVenta,
)
from src.modules.sales.infrastructure.repositories import ComprobanteRepo, VentaRepo
from src.modules.users.infrastructure.models import (
    Empresa,
    Grupo,
    Marca,
    Persona,
    Sucursal,
    Usuario,
)

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
    sucursal = Sucursal(
        marca_id=marca.id,
        empresa_id=empresa.id,
        nombre="Charlie's - Plaza",
        direccion="Jr. Ejemplo 123",
        tenencia="propia",
    )
    session.add(sucursal)
    session.flush()

    cat_udm = CategoriaUdm(nombre="Unidades")
    session.add(cat_udm)
    session.flush()
    unidad = UnidadMedida(
        categoria_udm_id=cat_udm.id, nombre="Unidad", ratio=Decimal(1)
    )
    session.add(unidad)
    session.flush()
    categoria = Categoria(empresa_id=empresa.id, nombre="Mercadería")
    session.add(categoria)
    session.flush()
    articulo = Articulo(
        empresa_id=empresa.id,
        id_interno="A001",
        nombre="Pizza",
        categoria_id=categoria.id,
        unidad_medida_id=unidad.id,
        tipo="mercaderia",
    )
    session.add(articulo)
    session.flush()
    receta = Receta(
        nombre="Pizza",
        rendimiento_cantidad=Decimal(1),
        rendimiento_unidad_medida_id=unidad.id,
    )
    session.add(receta)
    session.flush()
    session.add(
        RecetaItem(receta_id=receta.id, articulo_id=articulo.id, cantidad=Decimal(1))
    )

    productos = []
    for i, nombre in enumerate(("Pepperoni", "Hawaiana"), start=1):
        p = ProductoComercial(
            id_interno=f"P{i:03d}",
            marca_id=marca.id,
            nombre=nombre,
            receta_id=receta.id,
        )
        session.add(p)
        productos.append(p)
    session.flush()

    punto_venta = PuntoVenta(
        sucursal_id=sucursal.id,
        canal="trabajador",
        serie_boleta="B001",
        serie_factura="F001",
        politica_pago="al_finalizar",
    )
    session.add(punto_venta)
    persona = Persona(
        nombres="Ana",
        apellidos="Cajera",
        tipo_documento="dni",
        numero_documento="10000001",
    )
    session.add(persona)
    session.flush()
    usuario = Usuario(
        username="ana.cajera",
        pin_hash="fake",
        persona_id=persona.id,
        tipo="humano",
    )
    medio = MedioPago(
        empresa_id=empresa.id, nombre="Efectivo", direccion="cobro", tipo="efectivo"
    )
    session.add_all([usuario, medio])
    session.flush()

    return {
        "grupo": grupo,
        "empresa": empresa,
        "sucursal": sucursal,
        "productos": productos,
        "punto_venta": punto_venta,
        "usuario": usuario,
        "medio": medio,
    }


def _crear(session, base, items, **extra):
    return ventas_uc.crear_venta(
        session,
        sucursal_id=base["sucursal"].id,
        punto_venta_id=base["punto_venta"].id,
        canal="pdv",
        modalidad=extra.pop("modalidad", "mesa"),
        usuario_id=base["usuario"].id,
        idempotency_key=extra.pop("idempotency_key", f"key-{uuid.uuid4()}"),
        items=items,
        **extra,
    )


def _item(producto, cantidad=1, precio="40.00", grupo_cobro=1):
    return {
        "producto_comercial_id": producto.id,
        "cantidad": Decimal(cantidad),
        "precio_unitario": Decimal(precio),
        "grupo_cobro": grupo_cobro,
    }


# --- Mesa -------------------------------------------------------------------
def test_mesa_se_configura_por_sucursal_y_el_numero_es_unico(session, base):
    mesas_uc.crear_mesa(
        session, sucursal_id=base["sucursal"].id, numero=7, zona="Salón", capacidad=4
    )
    with pytest.raises(Conflicto):
        mesas_uc.crear_mesa(session, sucursal_id=base["sucursal"].id, numero=7)


def test_venta_en_mesa_de_otra_sucursal_se_rechaza(session, base):
    otra = Sucursal(
        marca_id=base["sucursal"].marca_id,
        empresa_id=base["empresa"].id,
        nombre="Charlie's - Otra",
        direccion="Jr. Otro 1",
        tenencia="propia",
    )
    session.add(otra)
    session.flush()
    mesa = mesas_uc.crear_mesa(session, sucursal_id=otra.id, numero=1)
    with pytest.raises(ReglaNegocio):
        _crear(session, base, [_item(base["productos"][0])], mesa_id=mesa.id)


def test_mesa_id_solo_aplica_a_modalidad_mesa(session, base):
    mesa = mesas_uc.crear_mesa(session, sucursal_id=base["sucursal"].id, numero=2)
    with pytest.raises(ReglaNegocio):
        _crear(
            session,
            base,
            [_item(base["productos"][0])],
            modalidad="delivery",
            mesa_id=mesa.id,
        )


def test_mapa_marca_ocupada_la_mesa_con_orden_abierta(session, base):
    libre = mesas_uc.crear_mesa(session, sucursal_id=base["sucursal"].id, numero=1)
    ocupada = mesas_uc.crear_mesa(session, sucursal_id=base["sucursal"].id, numero=2)
    _crear(
        session,
        base,
        [_item(base["productos"][0], cantidad=2)],
        mesa_id=ocupada.id,
        comensales=4,
    )
    mapa = {m.mesa.numero: m for m in mesas_uc.mapa(session, sucursal_id=base["sucursal"].id)}

    assert mapa[libre.numero].venta_id is None
    assert mapa[ocupada.numero].venta_id is not None
    assert mapa[ocupada.numero].comensales == 4
    assert mapa[ocupada.numero].total == Decimal("80.00")


def test_no_se_desactiva_una_mesa_con_orden_abierta(session, base):
    mesa = mesas_uc.crear_mesa(session, sucursal_id=base["sucursal"].id, numero=3)
    _crear(session, base, [_item(base["productos"][0])], mesa_id=mesa.id)
    with pytest.raises(Conflicto):
        mesas_uc.desactivar_mesa(session, mesa.id)


# --- Cobro dividido por grupos ----------------------------------------------
def test_cobrar_una_cuenta_no_cierra_la_venta_y_emite_su_comprobante(session, base):
    venta = _crear(
        session,
        base,
        [
            _item(base["productos"][0], precio="40.00", grupo_cobro=1),
            _item(base["productos"][1], precio="30.00", grupo_cobro=2),
        ],
    )
    _pago, venta, comprobante = ventas_uc.registrar_pago(
        session,
        venta_id=venta.id,
        medio_pago_id=base["medio"].id,
        monto=Decimal("40.00"),
        idempotency_key="pago-g1",
        grupo_cobro=1,
    )
    assert comprobante is not None, "la cuenta cubierta emite su comprobante"
    assert comprobante.grupo_cobro == 1
    assert venta.estado == "orden", "la cuenta 2 sigue pendiente"

    _pago2, venta, comprobante2 = ventas_uc.registrar_pago(
        session,
        venta_id=venta.id,
        medio_pago_id=base["medio"].id,
        monto=Decimal("30.00"),
        idempotency_key="pago-g2",
        grupo_cobro=2,
    )
    assert venta.estado == "pagada"
    assert comprobante2.id != comprobante.id
    assert len(ComprobanteRepo(session).todos_de_venta(venta.id)) == 2


def test_el_pago_no_puede_exceder_el_saldo_de_su_cuenta(session, base):
    venta = _crear(
        session,
        base,
        [
            _item(base["productos"][0], precio="40.00", grupo_cobro=1),
            _item(base["productos"][1], precio="30.00", grupo_cobro=2),
        ],
    )
    # 50 cabe en el total de la venta (70) pero no en la cuenta 1 (40).
    with pytest.raises(ReglaNegocio):
        ventas_uc.registrar_pago(
            session,
            venta_id=venta.id,
            medio_pago_id=base["medio"].id,
            monto=Decimal("50.00"),
            idempotency_key="pago-excede",
            grupo_cobro=1,
        )


def test_pagar_una_cuenta_inexistente_falla(session, base):
    venta = _crear(session, base, [_item(base["productos"][0])])
    with pytest.raises(NoEncontrado):
        ventas_uc.registrar_pago(
            session,
            venta_id=venta.id,
            medio_pago_id=base["medio"].id,
            monto=Decimal("10.00"),
            idempotency_key="pago-fantasma",
            grupo_cobro=9,
        )


def test_split_de_medios_dentro_de_una_misma_cuenta(session, base):
    """Efectivo + tarjeta sobre la misma cuenta: el comprobante recién sale
    cuando el saldo llega a cero."""
    venta = _crear(session, base, [_item(base["productos"][0], precio="40.00")])
    _p, venta, comprobante = ventas_uc.registrar_pago(
        session,
        venta_id=venta.id,
        medio_pago_id=base["medio"].id,
        monto=Decimal("15.00"),
        idempotency_key="parcial-1",
    )
    assert comprobante is None
    assert venta.estado == "orden"
    _p, venta, comprobante = ventas_uc.registrar_pago(
        session,
        venta_id=venta.id,
        medio_pago_id=base["medio"].id,
        monto=Decimal("25.00"),
        idempotency_key="parcial-2",
    )
    assert comprobante is not None
    assert venta.estado == "pagada"


# --- Receptor tecleado en caja ----------------------------------------------
@pytest.mark.parametrize(
    ("documento", "tipo", "serie"),
    [
        ("20601234567", "factura", "F001"),
        ("43219876", "boleta", "B001"),
        ("00000000", "boleta", "B001"),
        (None, "boleta", "B001"),
    ],
)
def test_el_documento_tecleado_decide_el_tipo_de_comprobante(
    session, base, documento, tipo, serie
):
    venta = _crear(session, base, [_item(base["productos"][0], precio="40.00")])
    _p, _v, comprobante = ventas_uc.registrar_pago(
        session,
        venta_id=venta.id,
        medio_pago_id=base["medio"].id,
        monto=Decimal("40.00"),
        idempotency_key=f"doc-{documento}",
        receptor_num_doc=documento,
        receptor_nombre="Cliente Prueba",
    )
    assert comprobante.tipo == tipo
    assert comprobante.serie == serie


def test_documento_a_medio_teclear_se_rechaza_antes_de_sunat(session, base):
    venta = _crear(session, base, [_item(base["productos"][0], precio="40.00")])
    with pytest.raises(ReglaNegocio):
        ventas_uc.registrar_pago(
            session,
            venta_id=venta.id,
            medio_pago_id=base["medio"].id,
            monto=Decimal("40.00"),
            idempotency_key="doc-corto",
            receptor_num_doc="1234",
        )


# --- Descuento manual de la orden -------------------------------------------
def test_descuento_exige_motivo_valido_y_sincroniza_el_total(session, base):
    venta = _crear(session, base, [_item(base["productos"][0], precio="100.00")])
    with pytest.raises(ReglaNegocio):
        ventas_uc.aplicar_descuento(
            session,
            venta_id=venta.id,
            modo="porcentaje",
            valor=Decimal(10),
            motivo="porque si",
            autorizado_por=base["usuario"].id,
        )

    venta = ventas_uc.aplicar_descuento(
        session,
        venta_id=venta.id,
        modo="porcentaje",
        valor=Decimal(10),
        motivo="cortesia",
        autorizado_por=base["usuario"].id,
    )
    assert venta.total == Decimal("90.00")
    assert venta.descuento_autorizado_por == base["usuario"].id


def test_el_descuento_se_reparte_entre_las_cuentas_a_prorrata(session, base):
    venta = _crear(
        session,
        base,
        [
            _item(base["productos"][0], precio="60.00", grupo_cobro=1),
            _item(base["productos"][1], precio="40.00", grupo_cobro=2),
        ],
    )
    ventas_uc.aplicar_descuento(
        session,
        venta_id=venta.id,
        modo="porcentaje",
        valor=Decimal(10),
        motivo="reclamo",
        autorizado_por=base["usuario"].id,
    )
    # 10% de 100 = 10, repartido 6 / 4 según lo que pesa cada cuenta.
    assert ventas_uc.total_a_cobrar(session, venta, 1) == Decimal("54.00")
    assert ventas_uc.total_a_cobrar(session, venta, 2) == Decimal("36.00")
    assert ventas_uc.total_a_cobrar(session, venta) == Decimal("90.00")


def test_descuento_quitado_devuelve_el_total_original(session, base):
    venta = _crear(session, base, [_item(base["productos"][0], precio="100.00")])
    ventas_uc.aplicar_descuento(
        session,
        venta_id=venta.id,
        modo="monto",
        valor=Decimal("25.00"),
        motivo="convenio",
        autorizado_por=base["usuario"].id,
    )
    assert venta.total == Decimal("75.00")
    venta = ventas_uc.aplicar_descuento(
        session,
        venta_id=venta.id,
        modo=None,
        valor=None,
        motivo=None,
        autorizado_por=base["usuario"].id,
    )
    assert venta.total == Decimal("100.00")
    assert venta.descuento_motivo is None


def test_no_se_cambia_el_descuento_de_una_venta_pagada(session, base):
    venta = _crear(session, base, [_item(base["productos"][0], precio="40.00")])
    ventas_uc.registrar_pago(
        session,
        venta_id=venta.id,
        medio_pago_id=base["medio"].id,
        monto=Decimal("40.00"),
        idempotency_key="pagada-ya",
    )
    with pytest.raises(Conflicto):
        ventas_uc.aplicar_descuento(
            session,
            venta_id=venta.id,
            modo="porcentaje",
            valor=Decimal(50),
            motivo="cortesia",
            autorizado_por=base["usuario"].id,
        )


# --- Cliente creado desde caja ----------------------------------------------
def test_ruc_de_once_digitos_crea_cliente_juridico(session, base):
    cliente = clientes_uc.crear_cliente(
        session,
        grupo_id=base["grupo"].id,
        nombre="Inversiones Nauta SAC",
        numero_documento="20601234567",
        direccion="Jr. Ramírez Hurtado 145",
    )
    assert cliente.tipo == "juridico"
    assert cliente.ruc == "20601234567"
    with pytest.raises(Conflicto):
        clientes_uc.crear_cliente(
            session,
            grupo_id=base["grupo"].id,
            nombre="Duplicado SAC",
            numero_documento="20601234567",
        )


def test_dni_crea_cliente_natural_y_reutiliza_la_persona_existente(session, base):
    cliente = clientes_uc.crear_cliente(
        session,
        grupo_id=base["grupo"].id,
        nombre="María Torres",
        numero_documento="43219876",
        telefono="942123456",
        direccion="Jr. San Martín 456",
    )
    assert cliente.tipo == "natural"
    assert cliente.persona_id is not None

    # La cajera de la fixture ya es persona: registrarla como cliente no
    # puede duplicar su documento (`persona.numero_documento` es único).
    otro = clientes_uc.crear_cliente(
        session,
        grupo_id=base["grupo"].id,
        nombre="Ana Cajera",
        telefono="988777666",
        numero_documento="10000001",
    )
    assert otro.persona_id == base["usuario"].persona_id


def test_solo_con_telefono_se_registra_un_cliente_natural(session, base):
    """El caso que más pasa en mostrador: el cliente no quiere dar su DNI."""
    cliente = clientes_uc.crear_cliente(
        session,
        grupo_id=base["grupo"].id,
        nombre="Jorge Vásquez",
        telefono="987654321",
        direccion="Av. Circunvalación 1200",
    )
    persona = session.get(Persona, cliente.persona_id)
    assert cliente.tipo == "natural"
    assert persona.numero_documento is None
    assert persona.telefono == "987654321"
    assert rules.cliente_identificado(persona.numero_documento) is False


def test_dos_clientes_sin_documento_no_chocan_entre_si(session, base):
    """El UNIQUE de `persona.numero_documento` admite varios NULL: dos
    anónimos seguidos no pueden bloquearse mutuamente."""
    for i, nombre in enumerate(("Uno Anonimo", "Dos Anonimo")):
        clientes_uc.crear_cliente(
            session,
            grupo_id=base["grupo"].id,
            nombre=nombre,
            telefono=f"90000000{i}",
        )
    session.flush()


def test_el_documento_generico_no_cuenta_como_identificado(session, base):
    cliente = clientes_uc.crear_cliente(
        session,
        grupo_id=base["grupo"].id,
        nombre="Cliente Varios",
        telefono="900111222",
        numero_documento=rules.SIN_DOCUMENTO,
    )
    persona = session.get(Persona, cliente.persona_id)
    # `00000000` se guarda como NULL: es "sin documento", no un documento.
    assert persona.numero_documento is None
    assert rules.cliente_identificado(rules.SIN_DOCUMENTO) is False


def test_cliente_sin_documento_ni_telefono_se_rechaza(session, base):
    with pytest.raises(ReglaNegocio):
        clientes_uc.crear_cliente(
            session, grupo_id=base["grupo"].id, nombre="Nadie"
        )


def test_documento_con_largo_invalido_se_rechaza(session, base):
    with pytest.raises(ReglaNegocio):
        clientes_uc.crear_cliente(
            session,
            grupo_id=base["grupo"].id,
            nombre="Documento Corto",
            telefono="900000000",
            numero_documento="123",
        )


def test_el_documento_se_completa_despues_y_pasa_a_identificado(session, base):
    cliente = clientes_uc.crear_cliente(
        session,
        grupo_id=base["grupo"].id,
        nombre="Rosa Delgado",
        telefono="965478123",
    )
    cliente = clientes_uc.actualizar_documento(
        session, cliente_id=cliente.id, numero_documento="40918273"
    )
    persona = session.get(Persona, cliente.persona_id)
    assert persona.numero_documento == "40918273"
    assert rules.cliente_identificado(persona.numero_documento) is True


def test_no_se_completa_con_un_documento_de_otra_persona(session, base):
    clientes_uc.crear_cliente(
        session,
        grupo_id=base["grupo"].id,
        nombre="Dueña Del Doc",
        telefono="900000001",
        numero_documento="43219876",
    )
    otro = clientes_uc.crear_cliente(
        session, grupo_id=base["grupo"].id, nombre="Otro", telefono="900000002"
    )
    with pytest.raises(Conflicto):
        clientes_uc.actualizar_documento(
            session, cliente_id=otro.id, numero_documento="43219876"
        )


def test_completar_documento_con_el_generico_se_rechaza(session, base):
    cliente = clientes_uc.crear_cliente(
        session, grupo_id=base["grupo"].id, nombre="Anonimo", telefono="900000003"
    )
    with pytest.raises(ReglaNegocio):
        clientes_uc.actualizar_documento(
            session, cliente_id=cliente.id, numero_documento=rules.SIN_DOCUMENTO
        )


def test_busqueda_encuentra_por_telefono_documento_y_nombre(session, base):
    clientes_uc.crear_cliente(
        session,
        grupo_id=base["grupo"].id,
        nombre="María Torres",
        telefono="942123456",
        numero_documento="43219876",
    )
    clientes_uc.crear_cliente(
        session,
        grupo_id=base["grupo"].id,
        nombre="Inversiones Nauta SAC",
        numero_documento="20601234567",
    )
    buscar = lambda q: clientes_uc.buscar(session, grupo_id=base["grupo"].id, q=q)  # noqa: E731

    assert len(buscar("942123456")) == 1, "por teléfono"
    assert len(buscar("43219876")) == 1, "por documento"
    assert len(buscar("Torres")) == 1, "por apellido"
    assert len(buscar("Nauta")) == 1, "por razón social"
    assert len(buscar("20601234567")) == 1, "por RUC"
    assert buscar("") == []


def test_una_persona_no_se_registra_dos_veces_como_cliente(session, base):
    clientes_uc.crear_cliente(
        session,
        grupo_id=base["grupo"].id,
        nombre="María Torres",
        telefono="942123456",
        numero_documento="43219876",
    )
    with pytest.raises(Conflicto):
        clientes_uc.crear_cliente(
            session,
            grupo_id=base["grupo"].id,
            nombre="María Torres",
            telefono="942123456",
            numero_documento="43219876",
        )


def test_boleta_de_cliente_sin_documento_sale_a_su_nombre(session, base):
    """Registrado solo por teléfono: el comprobante se emite igual, con el
    documento genérico pero con su nombre, no como 'clientes varios'."""
    cliente = clientes_uc.crear_cliente(
        session,
        grupo_id=base["grupo"].id,
        nombre="Jorge Vásquez",
        telefono="987654321",
    )
    receptor = comprobantes_uc._cliente_para_sunat(session, cliente)
    assert receptor.num_doc == rules.SIN_DOCUMENTO
    assert receptor.tipo_doc == rules.DOC_SUNAT_SIN_DOCUMENTO
    assert receptor.razon_social == "Jorge Vásquez"


# --- Compatibilidad hacia atrás ---------------------------------------------
def test_una_venta_sin_nada_nuevo_se_comporta_igual_que_antes(session, base):
    """El camino viejo (sin mesa, sin grupos, sin descuento, sin receptor)
    tiene que seguir dando un solo comprobante y cerrando la venta."""
    venta = _crear(
        session,
        base,
        [{"producto_comercial_id": base["productos"][0].id, "cantidad": Decimal(1),
          "precio_unitario": Decimal("40.00")}],
        modalidad="takeout",
        referencia_atencion="Carlos",
    )
    assert venta.mesa_id is None
    assert venta.total == Decimal("40.00")

    _p, venta, comprobante = ventas_uc.registrar_pago(
        session,
        venta_id=venta.id,
        medio_pago_id=base["medio"].id,
        monto=Decimal("40.00"),
        idempotency_key="compat-1",
    )
    assert venta.estado == "pagada"
    assert comprobante.grupo_cobro == rules.GRUPO_COBRO_UNICO
    # Clave histórica intacta: los comprobantes emitidos antes del cobro
    # dividido siguen resolviendo idempotentes.
    assert comprobante.idempotency_key == f"venta:{venta.id}"


def test_cobrar_dos_veces_la_misma_cuenta_no_duplica_el_comprobante(session, base):
    venta = _crear(session, base, [_item(base["productos"][0], precio="40.00")])
    ventas_uc.registrar_pago(
        session,
        venta_id=venta.id,
        medio_pago_id=base["medio"].id,
        monto=Decimal("40.00"),
        idempotency_key="idem-1",
    )
    primero = ComprobanteRepo(session).por_venta_y_grupo(venta.id, 1)
    segundo = comprobantes_uc.crear_comprobante_pendiente(session, venta, grupo_cobro=1)
    assert segundo.id == primero.id


def test_venta_del_dia_lista_lo_cobrado_en_la_jornada(session, base):
    from src.modules.sales.infrastructure.repositories import VentaRepo

    venta = _crear(session, base, [_item(base["productos"][0], precio="40.00")])
    ventas_uc.registrar_pago(
        session,
        venta_id=venta.id,
        medio_pago_id=base["medio"].id,
        monto=Decimal("40.00"),
        idempotency_key="jornada-1",
    )
    _crear(session, base, [_item(base["productos"][1], precio="30.00")])

    repo = VentaRepo(session)
    todas = repo.del_dia(sucursal_id=base["sucursal"].id, fecha=date.today())
    pagadas = repo.del_dia(
        sucursal_id=base["sucursal"].id, fecha=date.today(), estados=("pagada",)
    )
    assert len(todas) == 2
    assert [v.id for v in pagadas] == [venta.id]


# --- Extras de producto (RN-COM-021) ----------------------------------------
def _crear_extra(session, base, nombre, id_interno):
    """Un extra es un producto comercial con su propia receta."""
    extra = ProductoComercial(
        id_interno=id_interno,
        marca_id=base["sucursal"].marca_id,
        nombre=nombre,
        receta_id=base["productos"][0].receta_id,
        es_extra=True,
    )
    session.add(extra)
    session.flush()
    return extra


def test_extra_se_vende_como_linea_colgada_de_su_padre(session, base):
    extra = _crear_extra(session, base, "Extra queso", "E001")
    catalogo_uc.vincular_extra(
        session,
        producto_id=base["productos"][0].id,
        extra_id=extra.id,
        maximo=3,
    )
    venta = _crear(
        session,
        base,
        [
            {
                **_item(base["productos"][0], cantidad=2, precio="40.00"),
                "extras": [
                    {
                        "producto_comercial_id": extra.id,
                        "cantidad": Decimal(1),
                        "precio_unitario": Decimal("5.00"),
                    }
                ],
            }
        ],
    )
    filas = VentaRepo(session).items(venta.id)
    padres = [f for f in filas if f.padre_venta_item_id is None]
    hijos = [f for f in filas if f.padre_venta_item_id is not None]

    assert len(padres) == 1 and len(hijos) == 1
    assert hijos[0].padre_venta_item_id == padres[0].id
    # El extra hereda el grupo de cobro: dividir la cuenta no puede dejar
    # la pizza en una cuenta y su extra en otra.
    assert hijos[0].grupo_cobro == padres[0].grupo_cobro
    # El extra se pide POR PLATO: 2 pizzas con extra queso son 2 porciones.
    # 2×40 + 2×5 = 90. Cobrar una sola porción dejaría la segunda como
    # faltante de inventario.
    assert hijos[0].cantidad == Decimal(2)
    assert venta.total == Decimal("90.00")


def test_no_se_agrega_un_extra_que_el_producto_no_admite(session, base):
    extra = _crear_extra(session, base, "Extra tocino", "E002")
    with pytest.raises(ReglaNegocio):
        _crear(
            session,
            base,
            [
                {
                    **_item(base["productos"][0]),
                    "extras": [
                        {
                            "producto_comercial_id": extra.id,
                            "cantidad": Decimal(1),
                            "precio_unitario": Decimal("6.00"),
                        }
                    ],
                }
            ],
        )


def test_el_extra_respeta_su_tope_por_linea(session, base):
    extra = _crear_extra(session, base, "Extra queso", "E003")
    catalogo_uc.vincular_extra(
        session, producto_id=base["productos"][0].id, extra_id=extra.id, maximo=2
    )
    with pytest.raises(ReglaNegocio):
        _crear(
            session,
            base,
            [
                {
                    **_item(base["productos"][0]),
                    "extras": [
                        {
                            "producto_comercial_id": extra.id,
                            "cantidad": Decimal(5),
                            "precio_unitario": Decimal("5.00"),
                        }
                    ],
                }
            ],
        )


def test_un_producto_normal_no_puede_vincularse_como_extra(session, base):
    with pytest.raises(Conflicto):
        catalogo_uc.vincular_extra(
            session,
            producto_id=base["productos"][0].id,
            extra_id=base["productos"][1].id,
        )


def test_un_extra_no_admite_extras(session, base):
    extra = _crear_extra(session, base, "Extra queso", "E004")
    otro = _crear_extra(session, base, "Extra ají", "E005")
    with pytest.raises(Conflicto):
        catalogo_uc.vincular_extra(
            session, producto_id=extra.id, extra_id=otro.id
        )


def test_el_consumo_del_extra_se_multiplica_por_el_plato(session, base):
    """Dos pizzas con extra queso llevan dos porciones de queso."""
    extra = _crear_extra(session, base, "Extra queso", "E006")
    catalogo_uc.vincular_extra(
        session, producto_id=base["productos"][0].id, extra_id=extra.id
    )
    publicados = []
    event_bus.subscribe("sales.venta_confirmada", publicados.append)
    _crear(
        session,
        base,
        [
            {
                **_item(base["productos"][0], cantidad=3, precio="40.00"),
                "extras": [
                    {
                        "producto_comercial_id": extra.id,
                        "cantidad": Decimal(1),
                        "precio_unitario": Decimal("5.00"),
                    }
                ],
            }
        ],
    )
    items = publicados[-1]["items"]
    assert len(items) == 2, "el extra viaja como consumo propio a inventory"
    assert items[1]["cantidad"] == "3"


def test_el_extra_sobrevive_al_ida_y_vuelta_de_sincronizacion(session, base):
    """El extra se guarda con la cantidad total pero el request la espera
    por plato. Sin dividir al exportar, cada sincronización duplicaría los
    extras del local (ADR-009)."""
    from src.modules.sales.application.sincronizacion import _items_a_dict

    extra = _crear_extra(session, base, "Extra queso", "E007")
    catalogo_uc.vincular_extra(
        session, producto_id=base["productos"][0].id, extra_id=extra.id
    )
    venta = _crear(
        session,
        base,
        [
            {
                **_item(base["productos"][0], cantidad=3, precio="40.00"),
                "extras": [
                    {
                        "producto_comercial_id": extra.id,
                        "cantidad": Decimal(2),
                        "precio_unitario": Decimal("5.00"),
                    }
                ],
            }
        ],
    )
    filas = VentaRepo(session).items(venta.id)
    hijo = next(f for f in filas if f.padre_venta_item_id)
    assert hijo.cantidad == Decimal(6), "2 porciones × 3 platos"

    exportado = _items_a_dict(filas)
    assert len(exportado) == 1, "el extra viaja anidado, no como línea suelta"
    assert Decimal(exportado[0]["extras"][0]["cantidad"]) == Decimal(2), (
        "se exporta POR PLATO para que el replay no vuelva a multiplicar"
    )
