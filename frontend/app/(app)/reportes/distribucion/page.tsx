import { ApiError, apiFetch } from "@/lib/api";
import type { Area, MatrizFila } from "@/lib/reports";
import { obtenerSesion } from "@/lib/sesion";

import { DistribucionCliente } from "./distribucion-cliente";

export default async function DistribucionPage() {
  const { token } = await obtenerSesion();

  let matriz: MatrizFila[];
  try {
    matriz = await apiFetch<MatrizFila[]>("/api/v1/reports/matriz", { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el mapa de distribución."
        : "No se pudo cargar el mapa de distribución.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // Las áreas son contexto de la pantalla, no su dato central: si el usuario
  // puede ver la matriz pero no las áreas, la matriz igual se muestra.
  let areas: Area[] = [];
  try {
    areas = await apiFetch<Area[]>("/api/v1/reports/areas", { token });
  } catch {
    // silencioso a propósito, ver comentario arriba.
  }

  return <DistribucionCliente matriz={matriz} areas={areas} />;
}
