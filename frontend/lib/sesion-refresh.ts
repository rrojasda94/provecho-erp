/**
 * Renovación silenciosa de la sesión (ADR-073).
 *
 * El access token dura 15 minutos y el refresh 7 días, pero el frontend
 * nunca llamaba a `/auth/refresh`: la única lectura de la cookie de refresh
 * era el logout. Así que a los quince minutos la cookie de acceso caducaba y
 * el turno entero se iba a `/login` en medio de un pedido — el síntoma que
 * el personal reportó como "se desconecta solo".
 *
 * Vive acá y no en cada llamada porque la rotación **no admite dos intentos
 * con el mismo token**: `auth.refresh` marca el usado como revocado y trata
 * un segundo uso como señal de robo, revocando la sesión entera. Un PDV
 * dispara varias peticiones a la vez (carta, mesas, cuentas abiertas), así
 * que sin coordinación el propio arreglo cerraría la caja.
 */

import { API_INTERNAL_URL } from "@/lib/api";

export const COOKIE_TOKEN = "provecho_token";
export const COOKIE_REFRESH = "provecho_refresh";

export type ParDeTokens = { access_token: string; refresh_token: string };

/**
 * Renovaciones en vuelo, por token de refresh.
 *
 * Es un `Map` de módulo, así que su alcance es **un proceso de Next**. Con
 * un solo servidor —lo que hay hoy— cubre todas las pestañas de todas las
 * cajas, porque todas pegan contra el mismo proceso. Con más de una
 * instancia detrás de un balanceador, dos de ellas podrían rotar el mismo
 * token y revocar la sesión; queda anotado en Deuda técnica junto con el
 * resto de lo que asume una sola instancia.
 */
const enVuelo = new Map<string, Promise<ParDeTokens | null>>();

/**
 * Lo que se acaba de rotar, por el token **viejo**, durante unos segundos.
 *
 * Compartir solo la promesa en vuelo no alcanza, y esto se comprobó con la
 * sesión revocándose en la primera renovación real: una petición que ya
 * había salido con la cookie vieja llega *después* de que la rotación
 * terminó —el navegador todavía no tiene la cookie nueva— y no encuentra
 * nada en vuelo, así que pide otra rotación con un token ya marcado como
 * usado. La API lo lee como token robado y revoca la sesión entera, que es
 * exactamente lo que este archivo existe para evitar.
 *
 * Con la ventana de gracia, esa petición rezagada recibe el mismo par que la
 * primera. El precio es que un refresh robado y reusado **dentro de estos
 * segundos, contra este mismo proceso** no dispara la revocación: se le
 * devuelve el par que ya se había emitido. Se acepta a conciencia — la
 * detección de reuso sigue viva para todo lo demás, y la alternativa medida
 * es que la caja pierda la sesión cada quince minutos.
 */
const GRACIA_MS = 30_000;
const yaRotados = new Map<string, { tokens: ParDeTokens; hasta: number }>();

/** Saca lo vencido. Se hace acá y no con un temporizador porque el runtime
 * del middleware no garantiza que un `setTimeout` sobreviva al request. */
function podar(ahora: number): void {
  for (const [clave, entrada] of yaRotados) {
    if (entrada.hasta <= ahora) yaRotados.delete(clave);
  }
}

async function pedirRotacion(refresh: string): Promise<ParDeTokens | null> {
  try {
    const respuesta = await fetch(`${API_INTERNAL_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
      cache: "no-store",
    });
    if (!respuesta.ok) return null;
    return (await respuesta.json()) as ParDeTokens;
  } catch {
    // La API caída no es una sesión inválida: se devuelve `null` y el
    // llamador deja pasar la petición sin token, que es lo que ya hacía.
    return null;
  }
}

/**
 * Rota el par de tokens. Devuelve `null` si el refresh ya no vale (expirado,
 * reusado o revocado): ahí sí toca volver a `/login`.
 *
 * Las llamadas concurrentes con el mismo token comparten una sola rotación.
 */
export function refrescarSesion(refresh: string): Promise<ParDeTokens | null> {
  const ahora = Date.now();
  const reciente = yaRotados.get(refresh);
  if (reciente && reciente.hasta > ahora) return Promise.resolve(reciente.tokens);

  const yaVa = enVuelo.get(refresh);
  if (yaVa) return yaVa;

  const promesa = pedirRotacion(refresh)
    .then((tokens) => {
      if (tokens) {
        podar(ahora);
        yaRotados.set(refresh, { tokens, hasta: ahora + GRACIA_MS });
      }
      return tokens;
    })
    .finally(() => {
      // Se suelta al terminar y no antes: mientras la petición viaja,
      // cualquier otra con el mismo token tiene que esperar a esta en vez de
      // abrir una rotación paralela.
      enVuelo.delete(refresh);
    });
  enVuelo.set(refresh, promesa);
  return promesa;
}

/**
 * `secure` sigue a NODE_ENV salvo que se diga lo contrario. El override
 * existe para la demo portable, que se sirve por http sin TLS: desde otra
 * máquina de la red (`http://192.168.x.x:3000`, la tablet del local) el
 * navegador descarta una cookie `Secure` y el login falla **en silencio**.
 */
const ES_PRODUCCION = process.env.COOKIE_SECURE
  ? process.env.COOKIE_SECURE === "true"
  : process.env.NODE_ENV === "production";

/**
 * Opciones de cookie compartidas por el login y por la renovación.
 *
 * Compartidas y no copiadas: el navegador identifica una cookie por
 * `(nombre, dominio, path)`, así que si la renovación usara otro `path` el
 * resultado serían dos `provecho_token` distintos y ganaría el que no toca —
 * una sesión que se "renueva" y sigue caducando.
 *
 * **Sin `maxAge` a propósito (ADR-084).** Una cookie con `Max-Age` es
 * persistente: el navegador la escribe en disco y sobrevive a cerrar todas
 * las ventanas y a apagar el equipo, así que el refresh de siete días era una
 * ventana deslizante que ningún gesto del usuario cerraba. Sin plazo, el
 * navegador la borra al cerrarse, que es lo que la gente entiende por "cerrar
 * el sistema".
 *
 * Esto **no** rompe la renovación silenciosa de ADR-073. El disparador barato
 * era que el navegador borrara la cookie de acceso al vencer su `Max-Age`;
 * ahora ya no pasa, pero `convieneRenovar` lee el `exp` del JWT y dispara
 * igual — ese segundo camino existía justamente para el desfase entre los dos
 * relojes, y acá pasa a ser el único.
 *
 * Y no alcanza sola: "restaurar pestañas" devuelve las cookies de sesión tal
 * cual después de un apagón. El corte que no depende del navegador es el de
 * inactividad, y vive en la API (`REFRESH_INACTIVIDAD_HORAS`).
 */
export function opcionesCookie() {
  return {
    httpOnly: true,
    secure: ES_PRODUCCION,
    sameSite: "lax" as const,
    path: "/",
  };
}

/** Margen contra el vencimiento. Un token que le quedan diez segundos ya no
 * sirve: alcanza para que el request salga y no para que la API lo valide
 * del otro lado, y el resultado sería el mismo 401 que esto evita. */
const MARGEN_SEGUNDOS = 60;

/**
 * ¿Este access token ya no sirve, o está por dejar de servir?
 *
 * Se lee el `exp` del JWT **sin verificar la firma**, que es correcto acá:
 * la decisión no es de autorización —esa la toma la API en cada request—,
 * es "conviene renovar antes de mandarlo". Un token manipulado no gana nada
 * con esto: la API lo rechaza igual.
 *
 * Desde ADR-084 este es el **único** disparador. Antes había dos: la cookie
 * se plantaba con `maxAge` igual al plazo del token, así que el navegador la
 * borraba al vencer y su ausencia bastaba. Ahora la cookie es de sesión y no
 * caduca sola, de modo que el `exp` es lo que decide.
 *
 * Nunca fue redundante, además: son dos relojes distintos —el del navegador y
 * el del servidor de la API— y bastaba un desfase de segundos para que el
 * token venciera con la cookie todavía puesta. Esa ventana es exactamente el
 * 401 que dejaba a la caja en `/login` a mitad de un pedido.
 *
 * Un token ilegible cuenta como vencido: si no se puede leer, tampoco se
 * puede confiar en que sirva, y renovar es barato.
 */
export function convieneRenovar(token: string): boolean {
  try {
    const payload = token.split(".")[1];
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const { exp } = JSON.parse(atob(base64)) as { exp?: number };
    if (typeof exp !== "number") return true;
    return exp - Date.now() / 1000 < MARGEN_SEGUNDOS;
  } catch {
    return true;
  }
}
