/**
 * Rehace la base del e2e del sitio de marca desde cero. Corre **antes** de
 * `playwright test`, no como `globalSetup` — mismo motivo que
 * `frontend/e2e/preparar-bd.mjs`: en Windows, borrar el SQLite con la API
 * ya arriba revienta con `EPERM`.
 *
 * Además de `seed()` (marca, sucursales, permisos), esto deja el sitio en
 * condiciones de vender de verdad: un punto de venta `web` con delivery y
 * recojo habilitados por sucursal, una receta con stock (sin eso
 * `crear_venta` rechaza el pedido con "se vende por variante", RN-COM-022 —
 * ver `docs/roadmap/deuda/modulo-storefront.md`), y un producto con precio.
 */
import { execFileSync } from "node:child_process";
import { rmSync } from "node:fs";
import path from "node:path";

import { RAIZ, interprete } from "./interprete.mjs";

const PYTHON = interprete();
const DB = path.join(RAIZ, "storefront", "e2e.db");

const PREPARAR = `
from decimal import Decimal
from datetime import date

import src.core.models_registry  # noqa: F401
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import Base, engine
from src.modules.inventory.infrastructure.models import (
    Articulo, CategoriaUdm, Receta, RecetaItem, Sku, Stock, UnidadMedida,
)
from src.modules.sales.application import precios
from src.modules.sales.infrastructure.models import ProductoComercial, PuntoVenta
from src.modules.storefront.infrastructure.models import StorefrontPedido  # noqa: F401
from src.modules.users.infrastructure.models import Almacen, Empresa, Grupo, Marca, Sucursal
from src.seeders.seed import seed

Base.metadata.create_all(engine)
with Session(engine) as s:
    seed(s)
    empresa = s.scalar(select(Empresa))
    grupo = s.scalar(select(Grupo))
    marca = s.scalar(select(Marca).where(Marca.grupo_id == grupo.id))
    sucursales = list(s.scalars(select(Sucursal).where(Sucursal.marca_id == marca.id)))

    # Coordenadas de Tarapoto: hace falta algo real para que la cotización
    # de delivery no caiga siempre a "sin ubicar" (ver tarifa_delivery.py).
    coords = [(-6.499000, -76.359000), (-6.510000, -76.370000)]
    for sucursal, (lat, lng) in zip(sucursales, coords):
        sucursal.ubicacion_lat = Decimal(str(lat))
        sucursal.ubicacion_lng = Decimal(str(lng))
        if s.scalar(select(PuntoVenta).where(PuntoVenta.sucursal_id == sucursal.id, PuntoVenta.canal == "web")) is None:
            s.add(PuntoVenta(
                sucursal_id=sucursal.id, canal="web",
                serie_boleta="B00" + str(coords.index((lat, lng)) + 1),
                serie_factura="F00" + str(coords.index((lat, lng)) + 1),
                modalidades_habilitadas=["delivery", "takeout"],
                politica_pago="adelantado",
            ))
        if s.scalar(select(Almacen).where(Almacen.sucursal_id == sucursal.id)) is None:
            s.add(Almacen(empresa_id=empresa.id, sucursal_id=sucursal.id, nombre=f"WH-{sucursal.nombre}", tipo="sucursal"))
    s.flush()

    udm_cat = s.scalar(select(CategoriaUdm).where(CategoriaUdm.nombre == "Peso")) or CategoriaUdm(nombre="Peso")
    s.add(udm_cat)
    s.flush()
    udm = s.scalar(select(UnidadMedida).where(UnidadMedida.nombre == "Kilo")) or UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo")
    s.add(udm)
    s.flush()
    harina = s.scalar(select(Articulo).where(Articulo.id_interno == "E2E-HARINA"))
    if harina is None:
        harina = Articulo(empresa_id=empresa.id, id_interno="E2E-HARINA", nombre="Harina E2E", unidad_medida_id=udm.id, tipo="insumo")
        s.add(harina)
        s.flush()
    sku = s.scalar(select(Sku).where(Sku.articulo_id == harina.id)) or Sku(articulo_id=harina.id, codigo="SKU-E2E-HARINA")
    s.add(sku)
    s.flush()
    receta = s.scalar(select(Receta).where(Receta.nombre == "Pizza E2E storefront"))
    if receta is None:
        receta = Receta(empresa_id=empresa.id, nombre="Pizza E2E storefront", rendimiento_cantidad=Decimal(1), rendimiento_unidad_medida_id=udm.id)
        s.add(receta)
        s.flush()
        s.add(RecetaItem(receta_id=receta.id, articulo_id=harina.id, cantidad=Decimal("0.25")))
    for sucursal in sucursales:
        almacen = s.scalar(select(Almacen).where(Almacen.sucursal_id == sucursal.id))
        if s.scalar(select(Stock).where(Stock.almacen_id == almacen.id, Stock.sku_id == sku.id)) is None:
            s.add(Stock(almacen_id=almacen.id, sku_id=sku.id, cantidad=Decimal(500)))

    producto = s.scalar(select(ProductoComercial).where(ProductoComercial.id_interno == "E2E-PIZZA"))
    if producto is None:
        producto = ProductoComercial(id_interno="E2E-PIZZA", marca_id=marca.id, nombre="Pizza Storefront E2E", descripcion="Pizza para las pruebas del sitio.", receta_id=receta.id)
        s.add(producto)
        s.flush()
        lista = precios.crear_lista(s, marca_id=marca.id, nombre="General E2E", vigente_desde=date(2020, 1, 1))
        precios.fijar_precio(s, lista_precio_id=lista.id, producto_comercial_id=producto.id, monto=Decimal("29.90"))

    s.commit()
    print("base storefront e2e lista:", {"marca_id": str(marca.id), "producto_id": str(producto.id)})
`;

rmSync(DB, { force: true });

// Si `.next/` tiene una build de **producción** vieja (`prerender-manifest.json`,
// `server/`, `BUILD_ID` — quedan de un `npm run build` de verificación),
// `next dev` arranca en caliente con ese HTML/RSC ya prerenderizado en vez
// de renderizar en vivo, sirviendo la carta/checkout de datos que ya no
// existen (otro `marca_id`/`producto_id`) aunque el sitio y la API arranquen
// de cero. Mismo criterio que borrar `e2e.db`: `.next/` entero es estado
// descartable antes de cada corrida.
rmSync(path.join(RAIZ, "storefront", ".next"), { recursive: true, force: true });

execFileSync(PYTHON, ["-c", PREPARAR], {
  cwd: RAIZ,
  stdio: "inherit",
  env: { ...process.env, DATABASE_URL: "sqlite:///./storefront/e2e.db" },
});
