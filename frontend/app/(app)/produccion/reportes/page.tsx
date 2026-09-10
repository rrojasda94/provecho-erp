import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import type { Almacen } from "../ordenes-cliente";
import { ReportesCliente, type ReporteJornada } from "./reportes-cliente";

export default async function ReportesProduccionPage() {
  const { token } = await obtenerSesion();

  try {
    const [reportes, almacenes] = await Promise.all([
      apiFetch<Pagina<ReporteJornada>>("/api/v1/production/reportes-jornada", { token }),
      apiFetch<Almacen[]>("/api/v1/almacenes", { token }),
    ]);
    return (
      <ReportesCliente
        reportes={reportes.items}
        total={reportes.total}
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
