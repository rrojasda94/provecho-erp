import { ApiError, apiFetch, apiFetchCompleto } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import type { Almacen } from "../ordenes-cliente";
import { ReportesCliente, type ReporteJornada } from "./reportes-cliente";

export default async function ReportesProduccionPage() {
  const { token } = await obtenerSesion();

  try {
    const [reportes, almacenes] = await Promise.all([
      apiFetchCompleto<ReporteJornada>("/api/v1/production/reportes-jornada", { token }),
      apiFetch<Almacen[]>("/api/v1/almacenes", { token }),
    ]);
    return (
      <ReportesCliente
        reportes={reportes.items}
        almacenes={almacenes}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los reportes de producción."
        : "No se pudo cargar el reporte de producción.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
