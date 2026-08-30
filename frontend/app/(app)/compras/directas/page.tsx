import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import type { Almacen, Articulo, Proveedor } from "../ordenes-compra/ordenes-compra-cliente";
import { CompraDirectaCliente } from "./compra-directa-cliente";

/**
 * Compra directa: la compra y su factura en un paso (ADR-082).
 *
 * Ruta propia y no un diálogo dentro del listado de OC por dos razones. La
 * paleta de comandos y el sidebar leen `SUBMENUS`, así que un diálogo
 * escondido no se puede buscar por nombre — y «compra de mercado» es justo lo
 * que alguien va a buscar así. Y el formulario son proveedor, almacén, N
 * ítems y siete campos de factura: el diálogo de nueva OC ya es el más grande
 * del módulo.
 */
export default async function ComprasDirectasPage() {
  const { token } = await obtenerSesion();

  let proveedores: Pagina<Proveedor>;
  let almacenes: Almacen[];
  try {
    [proveedores, almacenes] = await Promise.all([
      apiFetch<Pagina<Proveedor>>("/api/v1/purchases/proveedores?page_size=200", {
        token,
      }),
      apiFetch<Almacen[]>("/api/v1/almacenes", { token }),
    ]);
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para registrar compras."
        : "No se pudo cargar proveedores y almacenes.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // De otro módulo: si inventory niega, la pantalla se dibuja con su aviso en
  // vez de caerse entera. Mismo criterio que el listado de OC.
  let articulos: Articulo[] = [];
  let avisoArticulos: string | null = null;
  try {
    articulos = (
      await apiFetch<Pagina<Articulo>>("/api/v1/inventory/articulos?page_size=200", {
        token,
      })
    ).items;
  } catch (e) {
    avisoArticulos =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el catálogo de artículos (inventory.leer)."
        : "No se pudo cargar el catálogo de artículos.";
  }

  return (
    <CompraDirectaCliente
      proveedores={proveedores.items}
      almacenes={almacenes}
      articulos={articulos}
      avisoArticulos={avisoArticulos}
    />
  );
}
