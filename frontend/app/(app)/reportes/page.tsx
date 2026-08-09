import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import type { ReporteEmitido } from "@/lib/reports";
import { obtenerSesion } from "@/lib/sesion";

import { MisReportesCliente } from "./mis-reportes-cliente";

export default async function MisReportesPage() {
  const { token } = await obtenerSesion();

  let reportes: ReporteEmitido[];
  try {
    reportes = (
      await apiFetch<Pagina<ReporteEmitido>>("/api/v1/reports/mios", { token })
    ).items;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver reportes."
        : "No se pudieron cargar tus reportes.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return <MisReportesCliente reportes={reportes} />;
}
