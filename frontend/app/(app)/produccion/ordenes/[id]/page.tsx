import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import type { Articulo } from "../../ordenes-cliente";
import { FichaOrdenCliente, type ConsumoSugerido, type OrdenDetalle } from "./ficha-cliente";

export default async function FichaOrdenPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { token } = await obtenerSesion();
  const { id } = await params;

  try {
    const [orden, articulos] = await Promise.all([
      apiFetch<OrdenDetalle>(`/api/v1/production/ordenes/${id}`, { token }),
      apiFetch<Pagina<Articulo>>("/api/v1/inventory/articulos?page_size=200", { token }),
    ]);
    let consumoSugerido: ConsumoSugerido | null = null;
    if (orden.estado === "borrador") {
      // Sin receta que produzca el artículo, el backend responde 409 — no
      // hay nada que sugerir, no es un error de la ficha.
      try {
        consumoSugerido = await apiFetch<ConsumoSugerido>(
          `/api/v1/production/ordenes/${id}/consumo-sugerido`,
          { token },
        );
      } catch {
        consumoSugerido = null;
      }
    }
    return (
      <FichaOrdenCliente
        orden={orden}
        consumoSugerido={consumoSugerido}
        articulos={articulos.items}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver esta orden."
        : e instanceof ApiError && e.status === 404
          ? "Orden de producción no encontrada."
          : "No se pudo cargar la orden de producción.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
