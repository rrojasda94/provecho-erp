"""Carta de pizzas armada con el modelo de nodos (solo desarrollo).

El catálogo de demo anterior modelaba cada combinación como un producto
plano —"Pizza pepperoni familiar", "Pizza hawaiana mediana"—, que es
justamente lo que el lienzo de nodos vino a reemplazar: con seis sabores y
tres tamaños serían dieciocho productos, dieciocho precios y dieciocho
recetas que mantener a mano.

Acá se carga como lo describe RN-PRD-004 y dibuja el lienzo:

    Pizza  →  tamaño (Personal/Mediana/Familiar)  →  Sabor (grupo obligatorio
              de una sola opción)  →  extras  →  restas  →  empaque

- **El tamaño es un producto hijo** con su receta base y su precio completo
  (RN-COM-022): la masa, la salsa y el queso cambian con el tamaño, no es la
  misma receta escalada.
- **El sabor es una opción de un grupo** `minimo=1, maximo=1` con **su propia
  receta** por tamaño: "Peperoni" en una Personal y en una Familiar llevan
  gramajes distintos, así que son dos recetas, no una.
- **Las restas no se cargan**: salen solas de los insumos de cada receta.

`--limpiar` desactiva lo que no es pizza en vez de borrarlo. Un producto ya
vendido se descontinúa, no se elimina (misma regla que `eliminar_producto`), y
además el catálogo de demo anterior no lo genera ningún seeder de este repo:
borrarlo sería destruir algo que nadie puede volver a crear.

Idempotente. **PROHIBIDO en producción**, igual que el resto de los seeders.

Uso:
    python -m src.seeders.pizzas_demo [--limpiar]
"""

import argparse
import sys
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
from src.modules.sales.application import catalogo as catalogo_uc
from src.modules.sales.application import precios as precios_uc
from src.modules.sales.infrastructure.models import ListaPrecio, ProductoComercial
from src.modules.sales.infrastructure.repositories import ProductoComercialRepo
from src.modules.users.infrastructure.models import Empresa, Marca

#: nombre → (unidad, costo unitario). El costo es lo que hace que el lienzo
#: pueda mostrar un margen: con todo en cero, "quitar un insumo baja el costo"
#: no se distingue de "nunca hubo costo".
INSUMOS: dict[str, tuple[str, str]] = {
    "Masa Cruda": ("Unidad", "1.20"),
    "Salsa De Tomate": ("Gramo", "0.004"),
    "Queso Mozzarella": ("Gramo", "0.028"),
    "Orégano": ("Gramo", "0.050"),
    "Peperoni": ("Gramo", "0.045"),
    "Piña": ("Gramo", "0.010"),
    "Jamón": ("Gramo", "0.032"),
    "Cebolla": ("Gramo", "0.006"),
    "Pimiento": ("Gramo", "0.009"),
    "Aceituna": ("Gramo", "0.038"),
    "Champiñón": ("Gramo", "0.052"),
    "Tocino": ("Gramo", "0.061"),
    "Caja Pizza": ("Unidad", "0.90"),
}

#: tamaño → (código, factor sobre la receta base, precio de lista)
TAMANOS: dict[str, tuple[str, Decimal, str]] = {
    "Personal": ("PZP", Decimal(1), "18.00"),
    "Mediana": ("PZM", Decimal(2), "32.00"),
    "Familiar": ("PZF", Decimal(3), "45.00"),
}

#: Lo que lleva toda pizza, sin importar el sabor (cantidades de la Personal).
BASE: list[tuple[str, int]] = [
    ("Masa Cruda", 1),
    ("Salsa De Tomate", 80),
    ("Queso Mozzarella", 150),
    ("Orégano", 2),
]

#: sabor → lo que agrega sobre la base, en cantidades de la Personal.
SABORES: dict[str, list[tuple[str, int]]] = {
    "Peperoni": [("Peperoni", 60), ("Aceituna", 20)],
    "Hawaiana": [("Piña", 70), ("Jamón", 50)],
    "Americana": [("Jamón", 60), ("Cebolla", 40), ("Pimiento", 30)],
    "Criolla": [("Cebolla", 50), ("Pimiento", 40), ("Aceituna", 25)],
    "Cuatro Quesos": [("Queso Mozzarella", 120)],
    "Vegetariana": [("Champiñón", 60), ("Pimiento", 40), ("Cebolla", 30)],
}

#: extra → (lo que agrega, precio)
EXTRAS: dict[str, tuple[list[tuple[str, int]], str]] = {
    "Extra Queso": ([("Queso Mozzarella", 80)], "6.00"),
    "Extra Peperoni": ([("Peperoni", 40)], "7.00"),
    "Extra Tocino": ([("Tocino", 40)], "8.00"),
    "Extra Champiñones": ([("Champiñón", 50)], "5.00"),
}

MERMA_QUESO = Decimal(3)
PADRE = "Pizza"


def _udm(session: Session, nombre: str, ratio: str) -> UnidadMedida:
    udm = session.scalar(select(UnidadMedida).where(UnidadMedida.nombre == nombre))
    if udm is not None:
        return udm
    categoria = session.scalar(select(CategoriaUdm))
    if categoria is None:
        categoria = CategoriaUdm(nombre="Unidades")
        session.add(categoria)
        session.flush()
    udm = UnidadMedida(
        categoria_udm_id=categoria.id,
        nombre=nombre,
        ratio=Decimal(ratio),
        decimales=2,
    )
    session.add(udm)
    session.flush()
    return udm


def _id_interno_libre(session: Session) -> str:
    """`articulo.id_interno` es VARCHAR(4): un hash no entra.

    SQLite no valida el largo y Postgres sí, así que un código de más
    caracteres pasa en las pruebas y revienta recién al sembrar de verdad.
    """
    tomados = set(session.scalars(select(Articulo.id_interno)))
    for n in range(1, 1000):
        codigo = f"I{n:03d}"
        if codigo not in tomados:
            return codigo
    raise RuntimeError("sin códigos de artículo libres con el prefijo I")


def _articulo(
    session: Session,
    empresa: Empresa,
    categoria: Categoria,
    nombre: str,
    udms: dict[str, UnidadMedida],
) -> Articulo:
    art = session.scalar(
        select(Articulo).where(
            Articulo.nombre == nombre, Articulo.empresa_id == empresa.id
        )
    )
    if art is not None:
        return art
    unidad, costo = INSUMOS[nombre]
    art = Articulo(
        empresa_id=empresa.id,
        id_interno=_id_interno_libre(session),
        nombre=nombre,
        categoria_id=categoria.id,
        unidad_medida_id=udms[unidad].id,
        tipo="insumo",
        costo_promedio=Decimal(costo),
    )
    session.add(art)
    session.flush()
    # Sin SKU activo el consumo de la venta no descuenta nada y queda una
    # incidencia; el lienzo se vería bien y el inventario no se movería.
    session.add(
        Sku(articulo_id=art.id, codigo=f"SKU-{art.id_interno}-{nombre[:8]}", prioridad=1)
    )
    session.flush()
    return art


def _receta(
    session: Session,
    empresa: Empresa,
    unidad: UnidadMedida,
    nombre: str,
    lineas: list[tuple[str, int]],
    articulos: dict[str, Articulo],
    factor: Decimal,
) -> Receta:
    receta = session.scalar(
        select(Receta).where(Receta.nombre == nombre, Receta.empresa_id == empresa.id)
    )
    if receta is not None:
        return receta
    receta = Receta(
        empresa_id=empresa.id,
        nombre=nombre,
        rendimiento_cantidad=Decimal(1),
        rendimiento_unidad_medida_id=unidad.id,
    )
    session.add(receta)
    session.flush()
    for insumo, cantidad in lineas:
        session.add(
            RecetaItem(
                receta_id=receta.id,
                articulo_id=articulos[insumo].id,
                cantidad=(Decimal(cantidad) * factor).quantize(Decimal("0.0001")),
                # El queso se pierde en el estirado: es la merma más real de
                # una pizzería y hace visible el campo en el lienzo.
                merma_pct=MERMA_QUESO if insumo == "Queso Mozzarella" else Decimal(0),
            )
        )
    session.flush()
    return receta


def _producto(session: Session, id_interno: str, **campos) -> ProductoComercial:
    existente = session.scalar(
        select(ProductoComercial).where(ProductoComercial.id_interno == id_interno)
    )
    if existente is not None:
        return existente
    return catalogo_uc.crear_producto(session, id_interno=id_interno, **campos)


def _precio(session: Session, lista, producto, monto: str) -> None:
    if lista is None:
        return
    try:
        precios_uc.fijar_precio(
            session,
            lista_precio_id=lista.id,
            producto_comercial_id=producto.id,
            monto=Decimal(monto),
        )
    except Exception:  # noqa: BLE001 — precio ya fijado: la lista es inmutable
        session.rollback()


def _tamano(
    session: Session,
    ctx: dict,
    tamano: str,
    codigo: str,
    factor: Decimal,
    precio: str,
) -> None:
    """Un tamaño: su receta base, su precio, su grupo de sabores y sus extras."""
    empresa, marca, unidad = ctx["empresa"], ctx["marca"], ctx["unidad"]
    articulos, padre, lista = ctx["articulos"], ctx["padre"], ctx["lista"]

    base = _receta(
        session, empresa, unidad, f"Pizza Base {tamano}", BASE, articulos, factor
    )
    variante = _producto(
        session,
        codigo,
        marca_id=marca.id,
        nombre=f"{PADRE} {tamano}",
        receta_id=base.id,
        producto_padre_id=padre.id,
        orden=list(TAMANOS).index(tamano),
    )
    catalogo_uc.editar_producto(
        session,
        variante.id,
        empaque_id=articulos["Caja Pizza"].id,
        # El empaque solo se consume fuera del salón (RN-EMP-003).
        modalidades_empaque=["takeout", "delivery"],
    )
    _precio(session, lista, variante, precio)

    # El sabor ES un grupo obligatorio de una sola opción: no hace falta un
    # tipo de grupo aparte en el modelo (ADR-035 §5).
    grupo = next(
        (g for g in ProductoComercialRepo(session).grupos_de(variante.id)
         if g.nombre == "Sabor"),
        None,
    )
    if grupo is None:
        grupo = catalogo_uc.crear_grupo_opcion(
            session, producto_id=variante.id, nombre="Sabor", minimo=1, maximo=1
        )

    for i, (sabor, lineas) in enumerate(SABORES.items()):
        receta = _receta(
            session, empresa, unidad, f"Sabor {sabor} {tamano}", lineas,
            articulos, factor,
        )
        opcion = _producto(
            session,
            f"S{list(TAMANOS).index(tamano)}{i}",
            marca_id=marca.id,
            nombre=sabor,
            receta_id=receta.id,
            es_extra=True,
        )
        _vincular(session, variante.id, opcion.id, grupo.id, maximo=1)
        # El sabor no cobra aparte —la variante ya lleva el precio completo
        # (RN-COM-022)—, pero **necesita precio de lista igual**: la carta
        # descarta todo extra sin precio vigente, y sin esta línea la pizza
        # sale sin sabores que elegir.
        _precio(session, lista, opcion, "0")

    for i, (extra, (lineas, monto)) in enumerate(EXTRAS.items()):
        receta = _receta(
            session, empresa, unidad, f"{extra} {tamano}", lineas, articulos, factor
        )
        prod = _producto(
            session,
            f"X{list(TAMANOS).index(tamano)}{i}",
            marca_id=marca.id,
            nombre=extra,
            receta_id=receta.id,
            es_extra=True,
        )
        _vincular(session, variante.id, prod.id, None, maximo=3)
        _precio(session, lista, prod, monto)


def _vincular(session, producto_id, extra_id, grupo_id, maximo) -> None:
    repo = ProductoComercialRepo(session)
    if repo.admite_extra(producto_id, extra_id) is not None:
        return
    catalogo_uc.vincular_extra(
        session,
        producto_id=producto_id,
        extra_id=extra_id,
        maximo=maximo,
        grupo_id=grupo_id,
    )


def _desactivar_lo_que_no_es_pizza(session: Session) -> list[str]:
    """Saca de la carta todo lo que no sea la pizza nueva.

    Desactiva, no borra: un producto con ventas no se puede eliminar sin
    perder el histórico, y este catálogo de demo no lo genera ningún seeder
    del repo — borrarlo sería destruir algo que nadie puede recrear.
    """
    nuestros = {PADRE, *(f"{PADRE} {t}" for t in TAMANOS), *SABORES, *EXTRAS}
    apagados = []
    for prod in session.scalars(select(ProductoComercial)):
        if prod.nombre in nuestros or not prod.activo:
            continue
        prod.activo = False
        apagados.append(prod.nombre)
    return apagados


def sembrar(session: Session, limpiar: bool = False) -> dict:
    empresa = session.scalar(select(Empresa))
    marca = session.scalar(select(Marca))
    if empresa is None or marca is None:
        raise RuntimeError("correr antes `python -m src.seeders.seed`")
    categoria = session.scalar(
        select(Categoria).where(Categoria.empresa_id == empresa.id)
    )
    if categoria is None:
        categoria = Categoria(empresa_id=empresa.id, nombre="Insumos")
        session.add(categoria)
        session.flush()

    udms = {
        "Unidad": _udm(session, "Unidad", "1"),
        "Gramo": _udm(session, "Gramo", "0.001"),
    }
    articulos = {n: _articulo(session, empresa, categoria, n, udms) for n in INSUMOS}

    # El padre agrupa y no se vende: sin receta ni precio (RN-COM-022).
    padre = _producto(session, "PZZA", marca_id=marca.id, nombre=PADRE)
    lista = session.scalar(select(ListaPrecio).where(ListaPrecio.activa.is_(True)))

    ctx = {
        "empresa": empresa,
        "marca": marca,
        "unidad": udms["Unidad"],
        "articulos": articulos,
        "padre": padre,
        "lista": lista,
    }
    for tamano, (codigo, factor, precio) in TAMANOS.items():
        _tamano(session, ctx, tamano, codigo, factor, precio)

    apagados = _desactivar_lo_que_no_es_pizza(session) if limpiar else []
    return {
        "producto": padre.nombre,
        "producto_id": str(padre.id),
        "tamanos": len(TAMANOS),
        "sabores": len(SABORES),
        "extras": len(EXTRAS),
        "desactivados": apagados,
    }


def main() -> None:
    if settings.es_produccion:
        print("ABORTA: seeder de demo prohibido en producción.", file=sys.stderr)
        raise SystemExit(1)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limpiar",
        action="store_true",
        help="desactiva de la carta todo lo que no sea esta pizza",
    )
    args = parser.parse_args()
    with SessionLocal() as session:
        datos = sembrar(session, limpiar=args.limpiar)
        session.commit()
    print(
        f"Carta de pizzas lista: {datos['tamanos']} tamaños × "
        f"{datos['sabores']} sabores + {datos['extras']} extras."
    )
    if datos["desactivados"]:
        print(f"Desactivados (no borrados): {', '.join(datos['desactivados'])}")
    print(f"Lienzo: /catalogo/productos/{datos['producto_id']}/nodos")


if __name__ == "__main__":
    main()
