import { cookies } from "next/headers";

/** Cookies de la cuenta de cliente (ADR-102) — prefijo propio, nunca las del
 * ERP (`provecho_token`/`provecho_refresh` de `frontend/`). httpOnly: el
 * JavaScript del navegador no las lee, solo el proceso de Next. */
export const COOKIE_TOKEN = "charlies_token";
export const COOKIE_REFRESH = "charlies_refresh";

export function opcionesCookie() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
  };
}

export type Claims = { sub: string; email: string; exp: number };

/** Decodifica el JWT sin verificar firma — solo para leer `email` y mostrarlo
 * en el header; ninguna decisión de autorización se toma acá (la API vuelve
 * a validar todo con su propio secreto). */
function decodificarClaims(token: string): Claims | null {
  try {
    const payload = token.split(".")[1];
    const json = Buffer.from(payload, "base64url").toString("utf-8");
    return JSON.parse(json) as Claims;
  } catch {
    return null;
  }
}

export type Sesion = { token: string; email: string } | null;

export async function obtenerSesion(): Promise<Sesion> {
  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) return null;
  const claims = decodificarClaims(token);
  if (!claims) return null;
  return { token, email: claims.email };
}
