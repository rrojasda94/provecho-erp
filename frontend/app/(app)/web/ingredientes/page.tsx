import { ApiError, apiFetch, apiFetchCompleto } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { IngredientesCliente, type Foto, type Insumo } from "./ingredientes-cliente";

export default async function WebIngredientesPage() {
  const { token } = await obtenerSesion();

  try {
    const insumos = await apiFetchCompleto<Insumo>(
      "/api/v1/inventory/articulos?tipo=insumo",
      { token },
    );

    // Una sola llamada para todas las fotos (antes: hasta 200 en paralelo).
    const ids = insumos.items.map((a) => `ids=${a.id}`).join("&");
    const fotosPorInsumo = insumos.items.length
      ? await apiFetch<Record<string, Foto[]>>(
          `/api/v1/storefront/fotos?entidad=ingrediente&${ids}`,
          { token },
        )
      : {};

    return <IngredientesCliente insumos={insumos.items} fotosPorInsumo={fotosPorInsumo} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los ingredientes del sitio web."
        : "No se pudieron cargar los ingredientes.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
