import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type Usuario = {
  id: string;
  username: string;
  tipo: string;
  roles: string[];
  sucursales: string[];
  empresa_id: string | null;
  permisos: string[];
};

export type Sesion = { token: string; usuario: Usuario };

/** Sesión del request: token de la cookie + `/users/me` real (no el JWT
 * decodificado sin verificar — los permisos deben venir de la fuente que
 * los resuelve, la API). Redirige a `/login` si no hay token o el token ya
 * no vale. Cada `layout.tsx` de módulo la llama de nuevo: es el guard
 * server-side real, no cachear entre capas por comodidad. */
export async function obtenerSesion(): Promise<Sesion> {
  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) redirect("/login");

  try {
    const usuario = await apiFetch<Usuario>("/api/v1/users/me", { token });
    return { token, usuario };
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect("/login");
    throw e;
  }
}
