import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  TrabajadoresCliente,
  type Cuenta,
  type Persona,
  type Sucursal,
  type Trabajador,
} from "./trabajadores-cliente";

/** Las cuentas se piden aparte y con red: listarlas exige `users.gestionar`,
 * que un rol de RRHH puro no tiene. Dentro del `Promise.all` un 403 tumbaría
 * la pantalla entera por un campo opcional; sin cuentas, el selector avisa
 * que hace falta administración y el resto del legajo se sigue editando. */
async function cuentasDisponibles(token: string): Promise<Cuenta[]> {
  try {
    const p = await apiFetch<Pagina<Cuenta>>("/api/v1/users", { token });
    return p.items;
  } catch {
    return [];
  }
}

export default async function TrabajadoresPage() {
  const { token } = await obtenerSesion();

  try {
    // `/personas/buscar`, no `/personas`: la tabla solo necesita nombre,
    // no la ficha completa, y así basta `personas.leer` — `users.gestionar`
    // ya no bloquea a un rol de RRHH puro (RN-GEN-007, gap cerrado).
    const [trabajadores, personas, sucursales, cuentas] = await Promise.all([
      apiFetch<Pagina<Trabajador>>("/api/v1/rrhh/trabajadores", { token }),
      apiFetch<Persona[]>("/api/v1/personas/buscar", { token }),
      // Catálogo de referencia: lo puede leer cualquier autenticado que tenga
      // que elegir una sucursal, no hace falta `organizacion.gestionar`.
      apiFetch<Sucursal[]>("/api/v1/sucursales", { token }),
      cuentasDisponibles(token),
    ]);
    return (
      <TrabajadoresCliente
        trabajadores={trabajadores.items}
        personas={personas}
        sucursales={sucursales}
        cuentas={cuentas}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver trabajadores."
        : "No se pudo cargar la lista de trabajadores.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
