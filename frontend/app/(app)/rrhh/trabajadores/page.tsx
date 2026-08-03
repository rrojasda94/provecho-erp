import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { TrabajadoresCliente, type Persona, type Trabajador } from "./trabajadores-cliente";

export default async function TrabajadoresPage() {
  const { token } = await obtenerSesion();

  try {
    // `/personas/buscar`, no `/personas`: la tabla solo necesita nombre,
    // no la ficha completa, y así basta `personas.leer` — `users.gestionar`
    // ya no bloquea a un rol de RRHH puro (RN-GEN-007, gap cerrado).
    const [trabajadores, personas] = await Promise.all([
      apiFetch<Trabajador[]>("/api/v1/rrhh/trabajadores", { token }),
      apiFetch<Persona[]>("/api/v1/personas/buscar", { token }),
    ]);
    return <TrabajadoresCliente trabajadores={trabajadores} personas={personas} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver trabajadores."
        : "No se pudo cargar la lista de trabajadores.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
