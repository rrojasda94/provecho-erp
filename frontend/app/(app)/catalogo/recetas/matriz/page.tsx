import { ApiError, apiFetch } from "@/lib/api";
import type { Grilla } from "@/lib/catalogo";
import { obtenerSesion } from "@/lib/sesion";

import { MatrizCliente } from "./matriz-cliente";

/**
 * El recetario en grilla (ADR-057).
 *
 * El filtro viaja en la URL y no en estado del cliente, igual que en el
 * listado: comparar tres recetas es un enlace que se pega en un chat, no un
 * estado que se pierde al recargar.
 */
type Params = Promise<{ recetas?: string }>;

export default async function MatrizPage({
  searchParams,
}: {
  searchParams: Params;
}) {
  const { token } = await obtenerSesion();
  const { recetas } = await searchParams;
  // La ruta va literal y el filtro como query aparte: `contrato.test.ts` lee
  // las rutas escritas a mano y no puede resolver una interpolada.
  const filtros = recetas ? `?receta_ids=${recetas}` : "";

  try {
    const grilla = await apiFetch<Grilla>(
      "/api/v1/inventory/recetas/matriz" + filtros,
      { token },
    );
    return <MatrizCliente grilla={grilla} filtro={recetas ?? ""} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las recetas."
        : "No se pudo cargar la matriz de recetas.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
