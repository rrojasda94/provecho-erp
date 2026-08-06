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
    const [ordenes, proveedores, almacenes, articulos] = await Promise.all([
      apiFetch<Pagina<OrdenCompra>>("/api/v1/purchases/ordenes-compra", { token }),
      apiFetch<Pagina<Proveedor>>("/api/v1/purchases/proveedores", { token }),
      apiFetch<Almacen[]>("/api/v1/almacenes", { token }),
      apiFetch<Pagina<Articulo>>("/api/v1/inventory/articulos", { token }),
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
