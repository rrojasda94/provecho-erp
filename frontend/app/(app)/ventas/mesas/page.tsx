import { ApiError, apiFetch } from "@/lib/api";
import { tienePermiso } from "@/lib/permisos";
import { obtenerSesion } from "@/lib/sesion";

import { MesasCliente, type Mesa, type Sucursal } from "./mesas-cliente";

function mensajeError(e: unknown, generico: string): string {
  return e instanceof ApiError && e.status === 403
    ? "Tu usuario no tiene permiso para ver esto."
    : generico;
}

/**
 * Configurar el salón: crear, editar y retirar mesas, y acomodarlas en el
 * plano. Hasta acá `mesa` solo se podía dar de alta por el seeder de demo
 * (ADR-018) — el PDV pintaba "esta sucursal no tiene mesas configuradas
 * todavía" sin ninguna pantalla que lo resolviera.
 *
 * `GET /sales/mesas` exige `sucursal_id` (no hay listado por empresa como
 * en puntos de venta): la sucursal activa vive en `?sucursal=`, así que
 * cambiarla es una navegación, no un fetch de cliente.
 */
export default async function MesasPage({
  searchParams,
}: {
  searchParams: Promise<{ sucursal?: string }>;
}) {
  const { token, usuario } = await obtenerSesion();
  const { sucursal } = await searchParams;

  let sucursales: Sucursal[];
  try {
    sucursales = await apiFetch<Sucursal[]>("/api/v1/sucursales", { token });
  } catch (e) {
    return <p className="text-secondary">{mensajeError(e, "No se pudieron cargar las sucursales.")}</p>;
  }

  const sucursalId = sucursal && sucursales.some((s) => s.id === sucursal)
    ? sucursal
    : sucursales[0]?.id;
  if (!sucursalId) {
    return <p className="text-gray">Todavía no hay sucursales creadas.</p>;
  }

  let mesas: Mesa[];
  try {
    mesas = await apiFetch<Mesa[]>(`/api/v1/sales/mesas?sucursal_id=${sucursalId}`, { token });
  } catch (e) {
    return <p className="text-secondary">{mensajeError(e, "No se pudieron cargar las mesas.")}</p>;
  }

  return (
    <MesasCliente
      mesas={mesas}
      sucursales={sucursales}
      sucursalId={sucursalId}
      puedeGestionar={tienePermiso(usuario.permisos, "sales.gestionar_mesas")}
    />
  );
}
