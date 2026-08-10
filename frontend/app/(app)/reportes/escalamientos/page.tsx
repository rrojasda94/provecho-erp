import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import type { Escalamiento } from "@/lib/reports";
import { obtenerSesion } from "@/lib/sesion";

import { EscalamientosCliente } from "./escalamientos-cliente";

type Params = Promise<{ nivel?: string; estado?: string }>;

export default async function EscalamientosPage({
  searchParams,
}: {
  searchParams: Params;
}) {
  const { token } = await obtenerSesion();
  const filtros = await searchParams;

  const query = new URLSearchParams();
  if (filtros.nivel) query.set("nivel_actual", filtros.nivel);
  if (filtros.estado) query.set("estado", filtros.estado);

  let escalamientos: Escalamiento[];
  try {
    escalamientos = (
      await apiFetch<Pagina<Escalamiento>>(
        `/api/v1/reports/escalamientos?${query}`,
        { token },
      )
    ).items;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Ver todos los escalamientos de la empresa exige `reports.leer_todo`."
        : "No se pudieron cargar los escalamientos.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return (
    <EscalamientosCliente
      escalamientos={escalamientos}
      nivel={filtros.nivel ?? ""}
      estado={filtros.estado ?? ""}
    />
  );
}
