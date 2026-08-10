import { ApiError, apiFetch } from "@/lib/api";
import type {
  CatalogoEmisiones,
  Escalamiento,
  ReporteEmitidoDetalle,
} from "@/lib/reports";
import { obtenerSesion } from "@/lib/sesion";

import { FichaReporte } from "./ficha-reporte";

export default async function ReportePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { token, usuario } = await obtenerSesion();

  let reporte: ReporteEmitidoDetalle;
  try {
    reporte = await apiFetch<ReporteEmitidoDetalle>(
      `/api/v1/reports/emitidos/${id}`,
      { token },
    );
  } catch (e) {
    const status = e instanceof ApiError ? e.status : 0;
    const mensaje =
      status === 403
        ? "Este reporte te fue entregado, pero su detalle exige el permiso del módulo dueño."
        : status === 404
          ? "Ese reporte no existe o no te fue entregado."
          : "No se pudo cargar el reporte.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // El catálogo y la cadena son contexto: si fallan, la ficha sigue sirviendo
  // para lo principal —qué pasó, quién y dónde— en vez de no mostrar nada.
  const [catalogo, escalamientos] = await Promise.all([
    apiFetch<CatalogoEmisiones>("/api/v1/reports/emisiones", { token }).catch(
      () => null,
    ),
    apiFetch<Escalamiento[]>(
      `/api/v1/reports/emitidos/${id}/escalamientos`,
      { token },
    ).catch(() => []),
  ]);

  return (
    <FichaReporte
      reporte={reporte}
      emision={catalogo?.emisiones.find((e) => e.codigo === reporte.codigo_emision) ?? null}
      destino={
        reporte.referencia_tipo
          ? (catalogo?.destinos[reporte.referencia_tipo] ?? null)
          : null
      }
      escalamientos={escalamientos}
      permisos={usuario.permisos}
    />
  );
}
