import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { PersonasCliente, type Persona } from "./personas-cliente";

export default async function PersonasPage() {
  const { token, usuario } = await obtenerSesion();

  let pagina: Pagina<Persona>;
  try {
    // `GET /personas` (ficha completa, `users.gestionar`), no
    // `/personas/buscar`: aquel devuelve solo nombre y documento a propósito
    // —es el selector de otro módulo— y con eso no se puede corregir nada.
    pagina = await apiFetch<Pagina<Persona>>("/api/v1/personas?page_size=200", {
      token,
    });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las fichas de personas."
        : "No se pudo cargar el listado de personas.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return (
    <PersonasCliente
      personas={pagina.items}
      total={pagina.total}
      permisos={usuario.permisos}
    />
  );
}
