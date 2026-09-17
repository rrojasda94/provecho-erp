import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { IngredientesCliente, type Foto, type Insumo } from "./ingredientes-cliente";

export default async function WebIngredientesPage() {
  const { token } = await obtenerSesion();

  try {
    const insumos = await apiFetch<Pagina<Insumo>>(
      "/api/v1/inventory/articulos?tipo=insumo&page_size=200",
      { token },
    );

    const fotos = await Promise.all(
      insumos.items.map((a) =>
        apiFetch<Foto[]>(`/api/v1/storefront/fotos/ingrediente/${a.id}`, { token }),
      ),
    );
    const fotosPorInsumo = Object.fromEntries(
      insumos.items.map((a, i) => [a.id, fotos[i]]),
    );

    return <IngredientesCliente insumos={insumos.items} fotosPorInsumo={fotosPorInsumo} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los ingredientes del sitio web."
        : "No se pudieron cargar los ingredientes.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
