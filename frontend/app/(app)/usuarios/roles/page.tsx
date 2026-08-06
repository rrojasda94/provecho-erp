import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { RolesCliente, type Permiso, type Rol } from "./roles-cliente";

export default async function RolesPage() {
  const { token } = await obtenerSesion();

  try {
    const [roles, permisos] = await Promise.all([
      apiFetch<Rol[]>("/api/v1/roles", { token }),
      apiFetch<Permiso[]>("/api/v1/permisos", { token }),
    ]);
    const permisosPorRol = Object.fromEntries(
      await Promise.all(
        roles.map(async (r) => [
          r.id,
          await apiFetch<Permiso[]>(`/api/v1/roles/${r.id}/permisos`, { token }),
        ]),
      ),
    );
    return <RolesCliente roles={roles} permisos={permisos} permisosPorRol={permisosPorRol} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para administrar roles."
        : "No se pudo cargar la lista de roles.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
