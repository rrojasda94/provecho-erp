import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { TrabajadoresCliente, type Persona, type Trabajador } from "./trabajadores-cliente";

export default async function TrabajadoresPage() {
  const { token } = await obtenerSesion();

  try {
    // GET /personas hoy exige `users.gestionar` (no solo `rrhh.leer`) — un
    // rol de RRHH puro sin ese permiso no puede armar el selector de alta,
    // aunque sí pueda leer trabajadores. Gap de RBAC conocido, ver ROADMAP.
    const [trabajadores, personas] = await Promise.all([
      apiFetch<Trabajador[]>("/api/v1/rrhh/trabajadores", { token }),
      apiFetch<Persona[]>("/api/v1/personas", { token }),
    ]);
    return <TrabajadoresCliente trabajadores={trabajadores} personas={personas} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver trabajadores (o para listar personas)."
        : "No se pudo cargar la lista de trabajadores.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
