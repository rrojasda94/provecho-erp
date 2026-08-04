import { ApiError, apiFetch } from "@/lib/api";
import type { Articulo, Categoria, UnidadMedida } from "@/lib/catalogo";
import { obtenerSesion } from "@/lib/sesion";

import { ArticulosCliente } from "./articulos-cliente";

export default async function ArticulosPage() {
  const { token } = await obtenerSesion();

  try {
    const [articulos, unidades, categorias] = await Promise.all([
      apiFetch<Articulo[]>("/api/v1/inventory/articulos", { token }),
      apiFetch<UnidadMedida[]>("/api/v1/inventory/unidades-medida", { token }),
      apiFetch<Categoria[]>("/api/v1/inventory/categorias", { token }),
    ]);
    return (
      <ArticulosCliente
        articulos={articulos}
        unidades={unidades}
        categorias={categorias}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el inventario."
        : "No se pudo cargar la lista de artículos.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
