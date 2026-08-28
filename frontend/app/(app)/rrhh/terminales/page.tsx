import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { TerminalesCliente, type Sucursal, type Terminal } from "./terminales-cliente";

export default async function TerminalesPage() {
  const { token } = await obtenerSesion();

  let sucursales: Sucursal[];
  try {
    sucursales = await apiFetch<Sucursal[]>("/api/v1/sucursales", { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los terminales."
        : "No se pudieron cargar las sucursales.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // Igual que en Turnos: el listado es por sucursal, y son dos o tres
  // locales — pedirlos en paralelo cuesta menos que inventar un endpoint
  // de empresa.
  const porSucursal = await Promise.all(
    sucursales.map((s) =>
      apiFetch<Terminal[]>(`/api/v1/rrhh/terminales?sucursal_id=${s.id}`, {
        token,
      }).catch(() => [] as Terminal[]),
    ),
  );

  return <TerminalesCliente terminales={porSucursal.flat()} sucursales={sucursales} />;
}
