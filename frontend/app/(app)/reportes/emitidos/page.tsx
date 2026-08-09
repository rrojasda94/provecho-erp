import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import type { ReporteEmitido } from "@/lib/reports";
import { obtenerSesion } from "@/lib/sesion";

import { EmitidosCliente } from "./emitidos-cliente";

export default async function EmitidosPage() {
  const { token } = await obtenerSesion();

  let reportes: ReporteEmitido[];
  try {
    reportes = (
      await apiFetch<Pagina<ReporteEmitido>>("/api/v1/reports/emitidos", { token })
    ).items;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver todos los reportes de la empresa."
        : "No se pudo cargar el historial de reportes emitidos.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return <EmitidosCliente reportes={reportes} />;
}
