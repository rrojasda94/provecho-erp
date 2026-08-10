import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { CategoriasCliente, type Categoria } from "./categorias-cliente";

export default async function CategoriasPage() {
  const { token } = await obtenerSesion();

  let categorias: Categoria[];
  try {
    categorias = await apiFetch<Categoria[]>("/api/v1/inventory/categorias", { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las categorías."
        : "No se pudo cargar el catálogo de categorías.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return <CategoriasCliente categorias={categorias} />;
}
