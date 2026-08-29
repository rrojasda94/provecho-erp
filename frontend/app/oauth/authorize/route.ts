import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

/**
 * `/oauth/authorize` — el único paso del SSO del BI (ADR-083 Fase B) que ve
 * el navegador de verdad.
 *
 * Vive en el frontend y no en la API a propósito: la sesión de Provecho es
 * una cookie httpOnly y host-only de este origen (`staging.majambo.com.pe`),
 * y la API vive en otro subdominio (`api-staging.majambo.com.pe`) al que esa
 * cookie nunca llega — ADR-004 no la amplía para evitar exponerla a todo
 * `*.majambo.com.pe`. Acá sí se puede leer, así que acá se decide si el
 * usuario está logueado y tiene `bi.acceder`, y quien de verdad emite el
 * código de un solo uso es la API (`POST /oauth/codigo`), no este archivo.
 *
 * `redirect_uri` **nunca** se usa para armar la redirección final antes de
 * que la API lo valide contra lo configurado: seguir un `redirect_uri` de la
 * URL de entrada sin esa validación sería un open redirect que además fuga
 * el código de autorización a quien lo haya armado.
 */
function alLogin(request: Request, url: URL) {
  const siguiente = `/oauth/authorize${url.search}`;
  return NextResponse.redirect(
    new URL(`/login?next=${encodeURIComponent(siguiente)}`, request.url),
  );
}

function errorJson(status: number, error: string, description: string) {
  return NextResponse.json({ error, error_description: description }, { status });
}

/** Cambia la excepción de `apiFetch` por la respuesta que le corresponde. */
function respuestaDeError(request: Request, url: URL, e: unknown) {
  // El token de la cookie venció entre el middleware y este request: mismo
  // camino que "sin sesión", no un error — la renovación silenciosa
  // (ADR-073) ya debería haberlo evitado, pero si no, reintentar el login es
  // lo que corresponde, no una pantalla de error.
  if (e instanceof ApiError && e.status === 401) return alLogin(request, url);
  if (e instanceof ApiError && e.status === 403) {
    return errorJson(403, "access_denied", "sin permiso bi.acceder");
  }
  return errorJson(502, "server_error", "no se pudo emitir el código");
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const clientId = url.searchParams.get("client_id");
  const redirectUri = url.searchParams.get("redirect_uri");
  const state = url.searchParams.get("state");
  const responseType = url.searchParams.get("response_type");

  if (responseType !== "code" || !clientId || !redirectUri) {
    return errorJson(400, "invalid_request", "faltan parámetros");
  }

  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  // Sin sesión: al login, con vuelta exacta a esta misma URL — quien entra a
  // Superset por primera vez sin haber abierto Provecho antes no puede
  // quedarse a mitad de camino.
  if (!token) return alLogin(request, url);

  let codigo: string;
  try {
    const respuesta = await apiFetch<{ codigo: string }>("/api/v1/oauth/codigo", {
      metodo: "POST",
      token,
      cuerpo: { client_id: clientId, redirect_uri: redirectUri },
    });
    codigo = respuesta.codigo;
  } catch (e) {
    return respuestaDeError(request, url, e);
  }

  // `redirectUri` ya pasó por la validación exacta de la API (si no
  // coincidía, `apiFetch` habría lanzado antes de llegar acá) — recién ahora
  // es seguro usarlo para construir la redirección final.
  const destino = new URL(redirectUri);
  destino.searchParams.set("code", codigo);
  if (state) destino.searchParams.set("state", state);
  return NextResponse.redirect(destino);
}
