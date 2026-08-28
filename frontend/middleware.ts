import { NextResponse, type NextRequest } from "next/server";

import {
  COOKIE_REFRESH,
  COOKIE_TOKEN,
  MAX_AGE_ACCESS,
  MAX_AGE_REFRESH,
  convieneRenovar,
  opcionesCookie,
  refrescarSesion,
  type ParDeTokens,
} from "@/lib/sesion-refresh";

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
 *
 * Los hosts de Google son de los campos de dirección (ADR-053): el SDK de
 * Maps se baja de `maps.googleapis.com`, habla con `*.googleapis.com` y trae
 * los tiles de `*.gstatic.com`. Van sin condicionar a que haya clave —una
 * CSP con dos formas es la que nadie prueba en las dos—, y la lista sale de
 * la guía oficial (`developers.google.com/maps/documentation/javascript/
 * content-security-policy`) recortada a lo que este ERP usa: sin Street View
 * ni `unsafe-eval`, que Google recomienda por las dudas y el mapa no
 * necesita. Si algún día un mapa muere con un error de `eval` en consola, esa
 * es la línea que falta y la decisión hay que volver a tomarla a conciencia.
 */
const GOOGLE_APIS = "https://*.googleapis.com";
const GOOGLE_ESTATICO = "https://*.gstatic.com";

/**
 * Renueva la sesión cuando la cookie de acceso ya venció (ADR-073).
 *
 * Va en el middleware y no en cada llamada porque es el único punto por el
 * que pasa TODO: el render de un server component, el proxy del navegador y
 * cualquier route handler. Poner el refresco en el proxy dejaba fuera al
 * render, y ponerlo en un latido del navegador no cubre a la pestaña que
 * estuvo quieta media hora y vuelve con un clic.
 *
 * Se dispara cuando la cookie de acceso no está —Next la planta con el mismo
 * plazo que el token, así que el navegador la borra al vencer— **o** cuando
 * el token que trae está por vencer. Lo segundo no sobra: son dos relojes
 * distintos, y basta un desfase de segundos entre el navegador y la API para
 * que el token muera con la cookie todavía puesta. Esa ventana es el 401 que
 * deja la caja en `/login` a mitad de un pedido.
 *
 * Además del `Set-Cookie`, reescribe la cookie del **request**: sin eso, la
 * petición que disparó la renovación seguiría viajando sin token y el
 * usuario vería un 401 antes de que la cookie nueva sirva de algo.
 */
async function renovarSesion(
  request: NextRequest,
  cabeceras: Headers,
): Promise<ParDeTokens | null> {
  const token = request.cookies.get(COOKIE_TOKEN)?.value;
  if (token && !convieneRenovar(token)) return null;
  const refresh = request.cookies.get(COOKIE_REFRESH)?.value;
  if (!refresh) return null;

  const tokens = await refrescarSesion(refresh);
  if (!tokens) return null;

  // Se **reemplaza**, no se agrega: con dos cookies del mismo nombre en la
  // cabecera, el parser de Next se queda con la primera, así que dejar el
  // token vencido delante haría que este viaje sin efecto. Reescribir la
  // lista entera no depende de en qué orden las mande el navegador.
  const otras = (cabeceras.get("cookie") ?? "")
    .split(";")
    .map((c) => c.trim())
    .filter((c) => c && !c.startsWith(`${COOKIE_TOKEN}=`));
  cabeceras.set(
    "cookie",
    [...otras, `${COOKIE_TOKEN}=${tokens.access_token}`].join("; "),
  );
  return tokens;
}


export async function middleware(request: NextRequest) {
  const nonce = crypto.randomUUID();
  const desarrollo = process.env.NODE_ENV !== "production";

  const csp = [
    "default-src 'self'",
    // `unsafe-eval` solo en dev: lo necesita el refresco en caliente.
    // `'strict-dynamic'` hace que los navegadores modernos IGNOREN la lista
    // de hosts: el SDK de Maps entra porque lo inserta un script ya
    // autorizado (`lib/google-maps.ts`). `maps.googleapis.com` queda como
    // respaldo para los que no soportan `strict-dynamic`, y `blob:` porque
    // el mapa levanta sus workers desde un blob.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic' https://maps.googleapis.com blob:${desarrollo ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com`,
    // Los tiles del mapa y los íconos del pin.
    `img-src 'self' data: blob: ${GOOGLE_APIS} ${GOOGLE_ESTATICO} https://*.google.com https://*.googleusercontent.com`,
    `font-src 'self' https://fonts.gstatic.com`,
    // El mapa levanta workers desde un blob; sin esto no dibuja.
    "worker-src blob:",
    // A la API del ERP el navegador sigue sin hablarle directo: sale por su
    // propio proxy (`app/api/proxy`), que es del mismo origen.
    //
    // Los hosts de Google son de los campos de dirección: el autocompletado
    // y el geocode inverso sí son fetch del navegador. La distancia de
    // reparto NO sale de acá —la calcula la API con su propia clave
    // (ADR-054)—, así que una llamada a `routes.googleapis.com` en la
    // pestaña de red del navegador es señal de que algo se implementó mal.
    //
    // En desarrollo se suma el WebSocket de recarga en caliente. `'self'` no
    // lo cubre en la práctica: Chrome no le reconoce el esquema `ws:` aunque
    // el origen coincida, así que dentro del contenedor la recarga moría con
    // un error de CSP en consola y había que reiniciar `web` para ver un
    // cambio.
    `connect-src 'self' ${GOOGLE_APIS} ${GOOGLE_ESTATICO} https://*.google.com blob: data:${desarrollo ? " ws: wss:" : ""}`,
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "upgrade-insecure-requests",
  ].join("; ");

  const cabeceras = new Headers(request.headers);
  cabeceras.set("x-nonce", nonce);
  cabeceras.set("Content-Security-Policy", csp);

  const renovados = await renovarSesion(request, cabeceras);

  const respuesta = NextResponse.next({ request: { headers: cabeceras } });
  respuesta.headers.set("Content-Security-Policy", csp);
  if (renovados) {
    respuesta.cookies.set(
      COOKIE_TOKEN,
      renovados.access_token,
      opcionesCookie(MAX_AGE_ACCESS),
    );
    // El refresh también rota (detección de reuso del lado de la API): si no
    // se guarda el nuevo, la próxima renovación mandaría el viejo y la API
    // lo leería como token robado, revocando la sesión entera.
    respuesta.cookies.set(
      COOKIE_REFRESH,
      renovados.refresh_token,
      opcionesCookie(MAX_AGE_REFRESH),
    );
  }
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
