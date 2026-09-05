import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { AreasCliente, type Area, type Miembro, type Opcion } from "./areas-cliente";

/**
 * Las áreas de distribución y quién las integra.
 *
 * El CRUD completo —crear área, renombrarla, sumar y quitar miembros— existía
 * en `reports` desde ADR-033 y **no lo llamaba ninguna pantalla**: el mapa de
 * distribución mostraba los huecos y las fugas, y no había forma de taparlos
 * salvo llamando la API a mano.
 */
export default async function AreasPage() {
  const { token, usuario } = await obtenerSesion();

  let areas: Area[];
  try {
    areas = await apiFetch<Area[]>("/api/v1/reports/areas", { token });
  } catch (e) {
    return (
      <p className="text-secondary">
        {e instanceof ApiError && e.status === 403
          ? "Tu usuario no tiene permiso para ver las áreas de reportes."
          : "No se pudieron cargar las áreas."}
      </p>
    );
  }

  const miembros = (
    await Promise.all(
      areas.map((a) =>
        apiFetch<Miembro[]>(`/api/v1/reports/areas/${a.id}/miembros`, { token }).catch(
          () => [] as Miembro[],
        ),
      ),
    )
  ).flat();

  // Roles, personas y sucursales son el catálogo con el que se arma un
  // miembro. Cada uno con su `catch`: quien administra la matriz no
  // necesariamente administra usuarios, y sin la lista igual se ve el área —
  // lo que no se puede es sumar por esa vía.
  const [roles, usuarios, sucursales] = await Promise.all([
    apiFetch<{ id: string; nombre: string }[]>("/api/v1/roles", { token }).catch(() => []),
    apiFetch<Pagina<{ id: string; username: string }>>("/api/v1/users?page_size=200", {
      token,
    })
      .then((p) => p.items.map((u) => ({ id: u.id, nombre: u.username })))
      .catch(() => [] as Opcion[]),
    apiFetch<Opcion[]>("/api/v1/sucursales", { token }).catch(() => [] as Opcion[]),
  ]);

  return (
    <AreasCliente
      areas={areas}
      miembros={miembros}
      roles={roles}
      usuarios={usuarios}
      sucursales={sucursales}
      permisos={usuario.permisos}
    />
  );
}
