import { ApiError, apiFetch } from "@/lib/api";
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
      apiFetch<OrdenCompra[]>("/api/v1/purchases/ordenes-compra", { token }),
      apiFetch<Proveedor[]>("/api/v1/purchases/proveedores", { token }),
      apiFetch<Almacen[]>("/api/v1/almacenes", { token }),
      apiFetch<Articulo[]>("/api/v1/inventory/articulos", { token }),
    ]);
    return (
      <OrdenesCompraCliente
        ordenes={ordenes}
        proveedores={proveedores}
        almacenes={almacenes}
        articulos={articulos}
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
