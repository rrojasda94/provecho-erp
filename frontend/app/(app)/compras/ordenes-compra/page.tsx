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

  try {
    // Los catálogos que alimentan un desplegable se piden al tope de página
    // (`PAGE_SIZE_MAXIMO`, 200) y no con el defecto de 50: el campo filtra sobre
    // lo que recibió, así que lo que no vino no existe para quien busca — y nada
    // en pantalla lo dice. Para el catálogo de artículos, que no cabe ni en 200,
    // el propio campo busca contra el servidor (`?q=`); esto es solo lo que
    // ofrece antes de teclear.
    const [ordenes, proveedores, almacenes, articulos] = await Promise.all([
      apiFetch<Pagina<OrdenCompra>>("/api/v1/purchases/ordenes-compra", { token }),
      apiFetch<Pagina<Proveedor>>("/api/v1/purchases/proveedores?page_size=200", {
        token,
      }),
      apiFetch<Almacen[]>("/api/v1/almacenes", { token }),
      apiFetch<Pagina<Articulo>>("/api/v1/inventory/articulos?page_size=200", {
        token,
      }),
    ]);
    return (
      <OrdenesCompraCliente
        ordenes={ordenes.items}
        proveedores={proveedores.items}
        almacenes={almacenes}
        articulos={articulos.items}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver órdenes de compra."
        : "No se pudo cargar las órdenes de compra.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
