"""Slice Venta de extremo a extremo: cadena completa de FKs + las dos
consultas que motivaron el slice: historial de compras del cliente y
ranking de ventas por trabajador.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Categoria,
    CategoriaUdm,
    Receta,
    RecetaItem,
    Sku,
    UnidadMedida,
)
from src.modules.rrhh.infrastructure.models import Trabajador
from src.modules.sales.infrastructure.models import (
    Cliente,
    ProductoComercial,
    PuntoVenta,
    Venta,
    VentaItem,
)
from src.modules.users.infrastructure.models import (
    Empresa,
    Grupo,
    Marca,
    Persona,
    Sucursal,
    Usuario,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _crear_cadena_base(session):
    """Organización + un artículo/producto/punto de venta mínimos."""
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
    unidad = UnidadMedida(categoria_udm_id=cat_udm.id, nombre="Unidad", ratio=Decimal(1))
    session.add(unidad)
    session.flush()

    categoria = Categoria(empresa_id=empresa.id, nombre="Mercadería")
    session.add(categoria)
    session.flush()

    articulo = Articulo(
        empresa_id=empresa.id,
        id_interno="A001",
        nombre="Pizza Familiar",
        categoria_id=categoria.id,
        unidad_medida_id=unidad.id,
        tipo="mercaderia",
    )
    session.add(articulo)
    session.flush()
    session.add(Sku(articulo_id=articulo.id, codigo="PZA-FAM-001"))

    receta = Receta(
        nombre="Pizza Familiar (venta directa)",
        rendimiento_cantidad=Decimal(1),
        rendimiento_unidad_medida_id=unidad.id,
    )
    session.add(receta)
    session.flush()
    session.add(RecetaItem(receta_id=receta.id, articulo_id=articulo.id, cantidad=Decimal(1)))

    producto = ProductoComercial(
        id_interno="P001",
        marca_id=marca.id,
        nombre="Pizza Familiar Clásica",
        receta_id=receta.id,
    )
    session.add(producto)
    session.flush()

    punto_venta = PuntoVenta(
        sucursal_id=sucursal.id,
        canal="trabajador",
        serie_boleta="B001",
        serie_factura="F001",
        politica_pago="al_finalizar",
    )
    session.add(punto_venta)
    session.flush()

    return empresa, sucursal, producto, punto_venta


def _crear_trabajador(session, empresa, nombre, apellido, documento):
    persona = Persona(
        nombres=nombre,
        apellidos=apellido,
        tipo_documento="dni",
        numero_documento=documento,
    )
    session.add(persona)
    session.flush()

    usuario = Usuario(
        username=f"{nombre.lower()}.{apellido.lower()}",
        pin_hash="argon2id$fake-hash-para-test",
        persona_id=persona.id,
        tipo="humano",
    )
    session.add(usuario)
    session.flush()

    trabajador = Trabajador(
        empresa_id=empresa.id,
        persona_id=persona.id,
        usuario_id=usuario.id,
        cargo="Cajero",
        area="Comercial",
        tipo_vinculo="planilla",
        fecha_ingreso=date(2026, 1, 15),
    )
    session.add(trabajador)
    session.flush()
    return usuario, trabajador


def test_historial_de_compras_por_cliente(session):
    empresa, sucursal, producto, punto_venta = _crear_cadena_base(session)
    usuario, _ = _crear_trabajador(session, empresa, "Ana", "Cajera", "10000001")

    grupo = session.get(Grupo, empresa.grupo_id)
    cliente = Cliente(grupo_id=grupo.id, tipo="natural", contacto="cliente@example.com")
    session.add(cliente)
    session.flush()

    for numero in range(1, 4):
        venta = Venta(
            sucursal_id=sucursal.id,
            fecha_orden=date(2026, 7, 20),
            numero_orden=numero,
            punto_venta_id=punto_venta.id,
            canal="pdv",
            modalidad="mesa",
            cliente_id=cliente.id,
            usuario_id=usuario.id,
            total=Decimal("45.00"),
            idempotency_key=str(uuid.uuid4()),
        )
        session.add(venta)
        session.flush()
        session.add(
            VentaItem(
                venta_id=venta.id,
                producto_comercial_id=producto.id,
                cantidad=Decimal(1),
                precio_unitario=Decimal("45.00"),
            )
        )
    session.commit()

    historial = session.scalars(
        select(Venta).where(Venta.cliente_id == cliente.id).order_by(Venta.created_at)
    ).all()
    assert len(historial) == 3
    assert all(v.total == Decimal("45.00") for v in historial)


def test_ranking_de_ventas_por_trabajador(session):
    empresa, sucursal, producto, punto_venta = _crear_cadena_base(session)
    usuario_ana, trabajador_ana = _crear_trabajador(
        session, empresa, "Ana", "Cajera", "10000002"
    )
    usuario_luis, trabajador_luis = _crear_trabajador(
        session, empresa, "Luis", "Mozo", "10000003"
    )

    montos = {usuario_ana.id: [Decimal("50"), Decimal("30")], usuario_luis.id: [Decimal("100")]}
    numero_orden = 1
    for usuario_id, ventas_montos in montos.items():
        for monto in ventas_montos:
            session.add(
                Venta(
                    sucursal_id=sucursal.id,
                    fecha_orden=date(2026, 7, 20),
                    numero_orden=numero_orden,
                    punto_venta_id=punto_venta.id,
                    canal="pdv",
                    modalidad="mesa",
                    usuario_id=usuario_id,
                    total=monto,
                    idempotency_key=str(uuid.uuid4()),
                )
            )
            numero_orden += 1
    session.commit()

    # Ranking: total vendido por trabajador (join usuario_id -> trabajador).
    ranking = session.execute(
        select(Trabajador.cargo, Trabajador.area, func.sum(Venta.total).label("total_vendido"))
        .join(Venta, Venta.usuario_id == Trabajador.usuario_id)
        .group_by(Trabajador.id)
        .order_by(func.sum(Venta.total).desc())
    ).all()

    assert ranking[0].total_vendido == Decimal("100")  # Luis
    assert ranking[1].total_vendido == Decimal("80")  # Ana (50+30)
    assert trabajador_ana.cargo == "Cajero"
    assert trabajador_luis.usuario_id == usuario_luis.id


def test_cliente_con_cuenta_web_acumula_historial_sin_login_en_sucursal(session):
    """cliente.usuario_id es opcional: la cuenta web es autoservicio, no un
    requisito para comprar en sucursal — ambos canales enrutan al mismo
    cliente.
    """
    empresa, sucursal, producto, punto_venta = _crear_cadena_base(session)
    usuario_cajero, _ = _crear_trabajador(session, empresa, "Ana", "Cajera", "10000004")

    persona_cliente = Persona(
        nombres="Rosa",
        apellidos="García",
        tipo_documento="dni",
        numero_documento="20000004",
        telefono="987654321",
    )
    session.add(persona_cliente)
    session.flush()

    cuenta_web = Usuario(
        username="rosa.garcia",
        pin_hash="argon2id$fake-hash-para-test",
        persona_id=persona_cliente.id,
        tipo="humano",
    )
    session.add(cuenta_web)
    session.flush()

    grupo = session.get(Grupo, empresa.grupo_id)
    cliente = Cliente(
        grupo_id=grupo.id,
        tipo="natural",
        persona_id=persona_cliente.id,
        usuario_id=cuenta_web.id,  # tiene cuenta web
        contacto=persona_cliente.telefono,
    )
    session.add(cliente)
    session.flush()

    # Compra en sucursal — sin login, solo referencia el mismo cliente_id
    # (en producción: encontrado por teléfono/DNI, lógica de aplicación).
    venta_sucursal = Venta(
        sucursal_id=sucursal.id,
        fecha_orden=date(2026, 7, 20),
        numero_orden=1,
        punto_venta_id=punto_venta.id,
        canal="pdv",
        modalidad="mesa",
        cliente_id=cliente.id,
        usuario_id=usuario_cajero.id,
        total=Decimal("60.00"),
        idempotency_key=str(uuid.uuid4()),
    )
    session.add(venta_sucursal)
    session.commit()

    historial = session.scalars(
        select(Venta).where(Venta.cliente_id == cliente.id)
    ).all()
    assert len(historial) == 1
    assert cliente.usuario_id == cuenta_web.id


def test_numero_orden_es_unico_por_sucursal_y_dia(session):
    empresa, sucursal, producto, punto_venta = _crear_cadena_base(session)
    usuario, _ = _crear_trabajador(session, empresa, "Ana", "Cajera", "10000005")

    session.add(
        Venta(
            sucursal_id=sucursal.id,
            fecha_orden=date(2026, 7, 20),
            numero_orden=1,
            punto_venta_id=punto_venta.id,
            canal="pdv",
            modalidad="mesa",
            usuario_id=usuario.id,
            total=Decimal("10.00"),
            idempotency_key=str(uuid.uuid4()),
        )
    )
    session.commit()

    session.add(
        Venta(
            sucursal_id=sucursal.id,
            fecha_orden=date(2026, 7, 20),
            numero_orden=1,  # mismo número, misma sucursal, mismo día
            punto_venta_id=punto_venta.id,
            canal="pdv",
            modalidad="mesa",
            usuario_id=usuario.id,
            total=Decimal("20.00"),
            idempotency_key=str(uuid.uuid4()),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
