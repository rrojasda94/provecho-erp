import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  TrabajadoresCliente,
  type Persona,
  type Sucursal,
  type Trabajador,
} from "./trabajadores-cliente";

export default async function TrabajadoresPage() {
  const { token, usuario } = await obtenerSesion();

  try {
    // `/personas/buscar`, no `/personas`: la tabla solo necesita nombre,
    // no la ficha completa, y así basta `personas.leer` — `users.gestionar`
    // ya no bloquea a un rol de RRHH puro (RN-GEN-007, gap cerrado). Por lo
    // mismo esta pantalla ya no pide `/api/v1/users` (ADR-070): la cuenta
    // con la que un trabajador marca se vincula y se ve en Usuarios, no acá.
    const [trabajadores, personas, sucursales] = await Promise.all([
      apiFetch<Pagina<Trabajador>>("/api/v1/rrhh/trabajadores", { token }),
      apiFetch<Persona[]>("/api/v1/personas/buscar", { token }),
      // Catálogo de referencia: lo puede leer cualquier autenticado que tenga
      // que elegir una sucursal, no hace falta `organizacion.gestionar`.
      apiFetch<Sucursal[]>("/api/v1/sucursales", { token }),
    ]);
    return (
      <TrabajadoresCliente
        trabajadores={trabajadores.items}
        personas={personas}
        sucursales={sucursales}
        permisos={usuario.permisos}
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
