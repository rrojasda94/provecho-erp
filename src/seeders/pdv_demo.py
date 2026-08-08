"""Datos de demo para operar el punto de venta (solo desarrollo).

`seed.py` deja la organización y los permisos, pero no deja nada que vender:
sin punto de venta, carta ni medios de pago, el PDV abre y no puede hacer
absolutamente nada. Esto completa lo que falta para tocar la pantalla de
punto a punto.

Crea una caja, un almacén de insumos mínimo, cuatro productos con su receta,
un extra que se agrega a las pizzas, una lista de precios vigente, medios de
pago y mesas del salón.

Idempotente: repetirlo no duplica nada. **PROHIBIDO en producción** — igual
que `seed.py`.

Uso:
    python -m src.seeders.pdv_demo
"""

import sys
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.config.settings import settings
from src.core.database import SessionLocal
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Categoria,
    CategoriaUdm,
    Receta,
    RecetaItem,
    Sku,
    UnidadMedida,
)
from src.modules.sales.infrastructure.models import (
    ListaPrecio,
    MedioPago,
    Mesa,
    Precio,
    ProductoComercial,
    ProductoComercialExtra,
    PuntoVenta,
)
from src.modules.users.infrastructure.models import Empresa, Marca, Persona, Sucursal

# (id_interno, nombre, precio, es_extra)
CARTA = [
    ("P001", "Pepperoni familiar", "42.00", False),
    ("P002", "Hawaiana mediana", "28.00", False),
    ("P003", "Inca Kola 1L", "9.00", False),
    ("P004", "Alitas BBQ x6", "24.00", False),
    ("E001", "Extra queso", "5.00", True),
]

# (nombres, apellidos, dni) — ninguna vinculada a un trabajador todavía; la
# demo de RRHH la usa para probar el alta de `trabajador` (persona_id
# existente es obligatorio, RN-GEN-007) sin depender de una pantalla de
# personas que todavía no existe en el frontend.
PERSONAS_DEMO = [
    ("Rosa", "Mendoza Vela", "70011223"),
    ("Carlos", "Ríos Pinedo", "70011224"),
]

MEDIOS = [
    ("Efectivo", "efectivo"),
    ("Yape", "billetera_digital"),
    ("Tarjeta", "tarjeta_debito"),
]


def _obtener_o_crear(session: Session, modelo, filtros: dict, **campos):
    fila = session.scalar(
        select(modelo).filter_by(**filtros)
    )
    if fila is not None:
        return fila
    fila = modelo(**filtros, **campos)
    session.add(fila)
    session.flush()
    return fila


def _receta_base(session: Session, empresa: Empresa) -> Receta:
    """Una receta mínima que todos los productos comparten. La demo no
    pretende costear bien: lo que importa es que exista la cadena
    producto → receta → artículo para que inventory descuente al vender."""
    cat_udm = _obtener_o_crear(session, CategoriaUdm, {"nombre": "Unidades"})
    unidad = _obtener_o_crear(
        session,
        UnidadMedida,
        {"nombre": "Unidad", "categoria_udm_id": cat_udm.id},
        ratio=Decimal(1),
    )
    categoria = _obtener_o_crear(
        session, Categoria, {"empresa_id": empresa.id, "nombre": "Mercadería"}
    )
    articulo = _obtener_o_crear(
        session,
        Articulo,
        {"empresa_id": empresa.id, "id_interno": "A001"},
        nombre="Insumo genérico de demo",
        categoria_id=categoria.id,
        unidad_medida_id=unidad.id,
        tipo="mercaderia",
    )
    _obtener_o_crear(session, Sku, {"articulo_id": articulo.id, "codigo": "DEMO-001"})

    receta = session.scalar(select(Receta).where(Receta.nombre == "Receta de demo"))
    if receta is None:
        receta = Receta(
            empresa_id=empresa.id,
            nombre="Receta de demo",
            rendimiento_cantidad=Decimal(1),
            rendimiento_unidad_medida_id=unidad.id,
        )
        session.add(receta)
        session.flush()
        session.add(
            RecetaItem(
                receta_id=receta.id, articulo_id=articulo.id, cantidad=Decimal(1)
            )
        )
    return receta


def _unidades_medida_demo(session: Session) -> None:
    """UdM extra para poder probar la pantalla de Artículos (inventory) más
    allá de "Unidad" — CRUD propio de `unidad_medida` sigue diferido, ver
    ROADMAP → Deuda técnica → Transversal."""
    for categoria_nombre, udm_nombre, decimales in (
        ("Peso", "Kilo", 3),
        ("Volumen", "Litro", 3),
    ):
        cat_udm = _obtener_o_crear(session, CategoriaUdm, {"nombre": categoria_nombre})
        _obtener_o_crear(
            session,
            UnidadMedida,
            {"nombre": udm_nombre, "categoria_udm_id": cat_udm.id},
            ratio=Decimal(1),
            decimales=decimales,
        )


def _personas_demo(session: Session) -> None:
    for nombres, apellidos, dni in PERSONAS_DEMO:
        _obtener_o_crear(
            session,
            Persona,
            {"numero_documento": dni},
            nombres=nombres,
            apellidos=apellidos,
            tipo_documento="dni",
        )


def sembrar(session: Session) -> None:
    empresa = session.scalar(select(Empresa))
    marca = session.scalar(select(Marca))
    sucursal = session.scalar(select(Sucursal).order_by(Sucursal.nombre))
    if not (empresa and marca and sucursal):
        raise SystemExit("Corre primero `python -m src.seeders.seed`.")

    punto = _obtener_o_crear(
        session,
        PuntoVenta,
        {"sucursal_id": sucursal.id, "canal": "trabajador"},
        serie_boleta="B001",
        serie_factura="F001",
        politica_pago="al_finalizar",
        modalidades_habilitadas=["mesa", "takeout", "delivery"],
    )

    for nombre, tipo in MEDIOS:
        _obtener_o_crear(
            session,
            MedioPago,
            {"empresa_id": empresa.id, "nombre": nombre},
            direccion="cobro",
            tipo=tipo,
        )

    for numero in range(1, 13):
        _obtener_o_crear(
            session,
            Mesa,
            {"sucursal_id": sucursal.id, "numero": numero},
            zona="Salón" if numero <= 8 else "Terraza",
            capacidad=4,
        )

    _unidades_medida_demo(session)
    _personas_demo(session)
    receta = _receta_base(session, empresa)
    productos = {}
    for id_interno, nombre, _precio, es_extra in CARTA:
        productos[id_interno] = _obtener_o_crear(
            session,
            ProductoComercial,
            {"id_interno": id_interno},
            marca_id=marca.id,
            nombre=nombre,
            receta_id=receta.id,
            es_extra=es_extra,
        )

    # El extra se ofrece solo sobre las pizzas: una gaseosa con extra queso
    # no es una venta, es un error de digitación (RN-COM-021).
    for id_pizza in ("P001", "P002"):
        if not session.scalar(
            select(ProductoComercialExtra).filter_by(
                producto_comercial_id=productos[id_pizza].id,
                extra_id=productos["E001"].id,
            )
        ):
            session.add(
                ProductoComercialExtra(
                    producto_comercial_id=productos[id_pizza].id,
                    extra_id=productos["E001"].id,
                    maximo=3,
                )
            )

    # Sin precio vigente el producto no sale en la carta (RN-PRC-003).
    lista = _obtener_o_crear(
        session,
        ListaPrecio,
        {"marca_id": marca.id, "nombre": "Carta regular"},
        vigente_desde=date(2020, 1, 1),
        activa=True,
        es_promocional=False,
    )
    for id_interno, _nombre, precio, _es_extra in CARTA:
        _obtener_o_crear(
            session,
            Precio,
            {
                "lista_precio_id": lista.id,
                "producto_comercial_id": productos[id_interno].id,
            },
            monto=Decimal(precio),
        )

    session.commit()
    print(
        f"PDV listo: sucursal {sucursal.nombre}, caja {punto.serie_boleta}, "
        f"{len(CARTA)} productos, {len(MEDIOS)} medios de pago, 12 mesas."
    )


def main() -> None:
    if settings.environment == "production":
        sys.exit("El seeder de demo no corre en producción.")
    with SessionLocal() as session:
        sembrar(session)


if __name__ == "__main__":
    main()
