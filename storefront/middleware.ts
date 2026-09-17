import { NextResponse, type NextRequest } from "next/server";

/**
 * Content-Security-Policy con nonce por request (ADR-103).
 *
 * Sin sesión: este sitio no tiene cookies de autenticación en PR1, así que
 * no hay nada que renovar acá — a diferencia de `frontend/middleware.ts`,
 * que además rota el refresh token del ERP.
 *
 * `strict-dynamic` deja que el bundle de Next (con nonce) cargue sus
 * propios chunks sin enumerar cada uno. Los hosts de Google son del SDK de
 * Maps (mapa de locales, `app/locales/`): habla con `*.googleapis.com` y
 * trae tiles de `*.gstatic.com`.
 *
 * `connect-src 'self'` y nada de la API del ERP: el navegador de este
 * sitio nunca le habla a la API directo — todo el contenido sale por
 * Server Components/Actions contra `API_INTERNAL_URL`, que corre en el
 * proceso de Next, no en el navegador (ADR-103 §7).
 */
const GOOGLE_APIS = "https://*.googleapis.com";
const GOOGLE_ESTATICO = "https://*.gstatic.com";

export function middleware(request: NextRequest) {
  const nonce = crypto.randomUUID();
  const desarrollo = process.env.NODE_ENV !== "production";

  const csp = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic' https://maps.googleapis.com blob:${desarrollo ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com`,
    `img-src 'self' data: blob: ${GOOGLE_APIS} ${GOOGLE_ESTATICO} https://*.google.com https://*.googleusercontent.com`,
    `font-src 'self' https://fonts.gstatic.com`,
    "worker-src blob:",
    `connect-src 'self' ${GOOGLE_APIS} ${GOOGLE_ESTATICO} https://*.google.com${desarrollo ? " ws: wss:" : ""}`,
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "upgrade-insecure-requests",
  ].join("; ");

  const cabeceras = new Headers(request.headers);
  cabeceras.set("x-nonce", nonce);
  cabeceras.set("Content-Security-Policy", csp);

  const respuesta = NextResponse.next({ request: { headers: cabeceras } });
  respuesta.headers.set("Content-Security-Policy", csp);
  return respuesta;
}

export const config = {
  matcher: [
    {
      source: "/((?!_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
