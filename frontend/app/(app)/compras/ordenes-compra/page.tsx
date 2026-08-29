import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  OrdenesCompraCliente,
  type Almacen,
  type Articulo,
  type OrdenCompra,
  type Proveedor,
} from "./ordenes-compra-cliente";

export default async function OrdenesCompraPage() {
  const { token } = await obtenerSesion();

  let ordenes: Pagina<OrdenCompra>;
  let proveedores: Pagina<Proveedor>;
  let almacenes: Almacen[];
  try {
    // El catálogo de proveedores alimenta un desplegable con búsqueda: se pide
    // al tope de página (`PAGE_SIZE_MAXIMO`, 200) y no con el defecto de 50,
    // porque el campo filtra sobre lo que recibió y lo que no vino no existe
    // para quien busca.
    [ordenes, proveedores, almacenes] = await Promise.all([
      apiFetch<Pagina<OrdenCompra>>("/api/v1/purchases/ordenes-compra", { token }),
      apiFetch<Pagina<Proveedor>>("/api/v1/purchases/proveedores?page_size=200", {
        token,
      }),
      apiFetch<Almacen[]>("/api/v1/almacenes", { token }),
    ]);
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver órdenes de compra."
        : "No se pudo cargar las órdenes de compra.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // El catálogo de artículos es de otro módulo (inventory): si falla, no
  // tumba la pantalla de compras — se muestra igual, sin poder elegir
  // artículo hasta que se resuelva el permiso/error de inventory.
  let articulos: Articulo[] = [];
  let avisoArticulos: string | null = null;
  try {
    articulos = (
      await apiFetch<Pagina<Articulo>>("/api/v1/inventory/articulos?page_size=200", { token })
    ).items;
  } catch (e) {
    avisoArticulos =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el catálogo de artículos (inventory.leer)."
        : "No se pudo cargar el catálogo de artículos.";
  }

  return (
    <OrdenesCompraCliente
      ordenes={ordenes.items}
      proveedores={proveedores.items}
      almacenes={almacenes}
      articulos={articulos}
      avisoArticulos={avisoArticulos}
    />
  );
}
