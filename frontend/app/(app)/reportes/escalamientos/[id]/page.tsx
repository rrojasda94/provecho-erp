import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import type { Escalamiento } from "@/lib/reports";
import { obtenerSesion } from "@/lib/sesion";

/**
 * Un escalamiento no tiene pantalla propia: **redirige al reporte que lo
 * originó**, donde ya viven la cadena, el historial y los botones (ADR-036).
 *
 * Duplicar el panel acá sería mantener dos vistas de lo mismo, y la que
 * importa es la que además muestra qué pasó y a dónde ir a resolverlo.
 */
export default async function EscalamientoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { token } = await obtenerSesion();

  let escalamiento: Escalamiento;
  try {
    escalamiento = await apiFetch<Escalamiento>(
      `/api/v1/reports/escalamientos/${id}`,
      { token },
    );
  } catch (e) {
    const status = e instanceof ApiError ? e.status : 0;
    const mensaje =
      status === 403
        ? "Ese escalamiento está fuera de tu alcance."
        : status === 404
          ? "Ese escalamiento no existe."
          : "No se pudo cargar el escalamiento.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  redirect(`/reportes/emitidos/${escalamiento.reporte_emitido_id}`);
}
