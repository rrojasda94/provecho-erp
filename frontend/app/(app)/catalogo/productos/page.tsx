import { ApiError, apiFetch } from "@/lib/api";
import type { Marca, Producto } from "@/lib/catalogo";
import { obtenerSesion } from "@/lib/sesion";

import { ProductosCliente } from "./productos-cliente";

export default async function ProductosPage() {
  const { token } = await obtenerSesion();

  try {
    const [productos, marcas] = await Promise.all([
      apiFetch<Producto[]>("/api/v1/sales/productos", { token }),
      apiFetch<Marca[]>("/api/v1/sales/marcas", { token }),
    ]);
    return <ProductosCliente productos={productos} marcas={marcas} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el catálogo comercial."
        : "No se pudo cargar el catálogo.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
