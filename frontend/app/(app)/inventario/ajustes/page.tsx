import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { AjustesCliente, type Ajuste } from "./ajustes-cliente";

type Params = Promise<{ ajuste?: string; estado?: string }>;

export default async function AjustesPage({
  searchParams,
}: {
  searchParams: Params;
}) {
  const { token, usuario } = await obtenerSesion();
  const filtros = await searchParams;

  // Sin filtro explícito se muestran los pendientes: la pantalla existe para
  // aprobarlos o rechazarlos, no para leer el histórico. Salvo que se llegue
  // desde un reporte, donde el ajuste puede estar ya resuelto.
  const estado = filtros.estado ?? (filtros.ajuste ? "" : "pendiente");

  let ajustes: Ajuste[];
  try {
    const query = new URLSearchParams(estado ? { estado } : {});
    ajustes = (
      await apiFetch<Pagina<Ajuste>>(`/api/v1/inventory/ajustes?${query}`, { token })
    ).items;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los ajustes de inventario."
        : "No se pudieron cargar los ajustes.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return (
    <AjustesCliente
      ajustes={ajustes}
      resaltado={filtros.ajuste ?? null}
      estado={estado}
      permisos={usuario.permisos}
    />
  );
}
