import { NextResponse, type NextRequest } from "next/server";

/**
 * Content-Security-Policy con nonce por request.
 *
 * Next inyecta scripts inline propios (hidratación, streaming de RSC), así
 * que una CSP sin nonce obligaría a `'unsafe-inline'` en `script-src` — que
 * es tanto como no tener CSP contra XSS. El nonce va en la cabecera del
 * *request*: Next lo lee de ahí y se lo pone solo a sus propios scripts.
 *
 * `'strict-dynamic'` deja que un script ya autorizado cargue sus chunks sin
 * tener que enumerar cada archivo de `/_next/static`.
 *
 * `style-src` sí lleva `'unsafe-inline'`: Next emite estilos críticos
 * inline y no les aplica nonce. Es la concesión conocida de este patrón —
 * el vector que importa (ejecución de script) queda cerrado igual.
 */
export function middleware(request: NextRequest) {
  const nonce = crypto.randomUUID();
  const desarrollo = process.env.NODE_ENV !== "production";

  const csp = [
    "default-src 'self'",
    // `unsafe-eval` solo en dev: lo necesita el refresco en caliente.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${desarrollo ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    // El navegador solo habla con este origen: el frontend llega a la API
    // por su propio proxy (`app/api/proxy`), no por fetch cruzado.
    "connect-src 'self'",
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
    // Los estáticos no necesitan CSP y pagarían el costo de pasar por acá.
    {
      source: "/((?!_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
