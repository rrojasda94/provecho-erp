import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { PermisosCliente, type Solicitud, type TrabajadorRef } from "./permisos-cliente";

type Trabajador = { id: string; persona_id: string; estado: string };
type Persona = { id: string; nombres: string; apellidos: string };

/**
 * La bandeja de aprobación de permisos.
 *
 * `GET /rrhh/solicitudes-permiso` existía **con su filtro de estado y su
 * consulta ya escrita** («la bandeja de aprobación, sin ejecutar»), y no la
 * llamaba ninguna pantalla: un permiso solo se podía pedir y aprobar por API.
 */
export default async function PermisosPage({
  searchParams,
}: {
  searchParams: Promise<{ estado?: string }>;
}) {
  const { token, usuario } = await obtenerSesion();
  const { estado } = await searchParams;
  // Sin `?estado=` explícito se abre en pendientes: quien entra acá entra por
  // «qué tengo que resolver», no por el histórico.
  const soloPendientes = estado === undefined;

  try {
    const query = new URLSearchParams(soloPendientes ? { estado: "pendiente" } : {});
    const [solicitudes, trabajadores, personas] = await Promise.all([
      apiFetch<Pagina<Solicitud>>(`/api/v1/rrhh/solicitudes-permiso?${query}`, { token }),
      apiFetch<Pagina<Trabajador>>("/api/v1/rrhh/trabajadores", { token }),
      apiFetch<Persona[]>("/api/v1/personas/buscar", { token }),
    ]);

    const nombrePersona = new Map(
      personas.map((p) => [p.id, `${p.nombres} ${p.apellidos}`.trim()] as const),
    );
    const refs: TrabajadorRef[] = trabajadores.items.map((t) => ({
      id: t.id,
      estado: t.estado,
      nombre: nombrePersona.get(t.persona_id) ?? "trabajador",
    }));

    return (
      <PermisosCliente
        solicitudes={solicitudes.items}
        trabajadores={refs}
        permisos={usuario.permisos}
        soloPendientes={soloPendientes}
      />
    );
  } catch (e) {
    return (
      <p className="text-secondary">
        {e instanceof ApiError && e.status === 403
          ? "Tu usuario no tiene permiso para ver las solicitudes de permiso."
          : "No se pudieron cargar las solicitudes de permiso."}
      </p>
    );
  }
}
