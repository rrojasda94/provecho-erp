import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { TurnosCliente, type Sucursal, type Turno } from "./turnos-cliente";

export default async function TurnosPage() {
  const { token } = await obtenerSesion();

  let sucursales: Sucursal[];
  try {
    sucursales = await apiFetch<Sucursal[]>("/api/v1/sucursales", { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los turnos."
        : "No se pudieron cargar las sucursales.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // El listado de turnos es por sucursal —un turno siempre es de un local—,
  // así que la pantalla de administración los junta. Son dos o tres locales:
  // pedirlos en paralelo cuesta menos que inventar un endpoint de empresa.
  const porSucursal = await Promise.all(
    sucursales.map((s) =>
      apiFetch<Turno[]>(`/api/v1/rrhh/turnos?sucursal_id=${s.id}`, { token }).catch(
        () => [] as Turno[],
      ),
    ),
  );

  return <TurnosCliente turnos={porSucursal.flat()} sucursales={sucursales} />;
}
