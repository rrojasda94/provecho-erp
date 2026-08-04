import { ApiError, apiFetch } from "@/lib/api";
import type { Receta, UnidadMedida } from "@/lib/catalogo";
import { obtenerSesion } from "@/lib/sesion";

import { RecetasCliente } from "./recetas-cliente";

export default async function RecetasPage() {
  const { token } = await obtenerSesion();

  try {
    const [recetas, unidades] = await Promise.all([
      apiFetch<Receta[]>("/api/v1/inventory/recetas", { token }),
      apiFetch<UnidadMedida[]>("/api/v1/inventory/unidades-medida", { token }),
    ]);
    return <RecetasCliente recetas={recetas} unidades={unidades} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las recetas."
        : "No se pudo cargar la lista de recetas.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
