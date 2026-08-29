import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import type { Articulo, RecetaDetalle, UnidadMedida } from "@/lib/catalogo";
import { obtenerSesion } from "@/lib/sesion";

import { FichaReceta } from "./ficha-receta";

export default async function RecetaPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { token } = await obtenerSesion();

  try {
    const [receta, articulos, unidades] = await Promise.all([
      apiFetch<RecetaDetalle>(`/api/v1/inventory/recetas/${id}`, { token }),
      // Sin `page_size`, la API corta en 50: el selector de "artículo que
      // produce esta receta" (`subrecetas`) se queda sin decirlo en cuanto
      // el catálogo pasa de una página.
      apiFetch<Pagina<Articulo>>("/api/v1/inventory/articulos?page_size=200", {
        token,
      }),
      apiFetch<UnidadMedida[]>("/api/v1/inventory/unidades-medida", { token }),
    ]);
    return <FichaReceta receta={receta} articulos={articulos.items} unidades={unidades} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver esta receta."
        : "No se pudo cargar la receta.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
