import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type Paleta = "estandar" | "alto_contraste";
export type TamanoFuente = "estandar" | "grande" | "muy_grande" | "maximo";
export type Tema = "claro" | "oscuro";

export type Usuario = {
  id: string;
  username: string;
  tipo: string;
  roles: string[];
  sucursales: string[];
  empresa_id: string | null;
  permisos: string[];
  preferencia_paleta: Paleta;
  preferencia_tamano_fuente: TamanoFuente;
  preferencia_tema: Tema;
};

export type Sesion = { token: string; usuario: Usuario };

export const PREFERENCIAS_POR_DEFECTO = {
  preferencia_paleta: "estandar",
  preferencia_tamano_fuente: "estandar",
  preferencia_tema: "claro",
} as const;

/** Sesión del request: token de la cookie + `/users/me` real (no el JWT
 * decodificado sin verificar — los permisos deben venir de la fuente que
 * los resuelve, la API). Redirige a `/login` si no hay token o el token ya
 * no vale. Cada `layout.tsx` de módulo la llama de nuevo: es el guard
 * server-side real, no cachear entre capas por comodidad — Next.js App
 * Router no pasa props de un layout a otro. Puede llegar a llamarse 3
 * veces por request (layout raíz + layout de módulo + page); se asume que
 * la memoización de `fetch` de Next.js (mismo GET + mismos headers, mismo
 * render pass) las reduce a una sola llamada real de red. Si `apiFetch`
 * cambia de forma (headers dinámicos, etc.) esa dedup se pierde en
 * silencio — no hay nada en el código que lo garantice. */
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

/**
 * Preferencias de presentación para el layout raíz, que también sirve
 * `/login`, `/pdv` y `/kds` — pantallas sin sesión o fuera del shell. Por eso
 * no redirige ni lanza: sin sesión devuelve los valores por defecto.
 *
 * Se resuelve en el servidor y no en el cliente a propósito. La alternativa
 * habitual (`next-themes` + localStorage) necesita un script inline que corra
 * antes de pintar, y la CSP de `middleware.ts` firma los scripts con un nonce
 * por request: sería abrirle un agujero al único control que de verdad
 * protege contra XSS, para evitar un parpadeo que así no existe.
 */
export async function obtenerPreferencias() {
  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) return PREFERENCIAS_POR_DEFECTO;

  try {
    const usuario = await apiFetch<Usuario>("/api/v1/users/me", { token });
    return {
      preferencia_paleta: usuario.preferencia_paleta,
      preferencia_tamano_fuente: usuario.preferencia_tamano_fuente,
      preferencia_tema: usuario.preferencia_tema,
    };
  } catch {
    // Un fallo acá no puede tumbar la aplicación entera: el peor caso es que
    // alguien vea el ERP en tamaño estándar durante un request.
    return PREFERENCIAS_POR_DEFECTO;
  }
}
