/**
 * Cliente HTTP del NAVEGADOR hacia la API. Todo pasa por `/api/proxy` (ver
 * `app/api/proxy/[...ruta]/route.ts`): el token vive en una cookie httpOnly
 * y nunca llega al JavaScript de la página.
 *
 * Vive aparte de `lib/pdv.ts` porque ya hay dos pantallas táctiles fuera del
 * shell (PDV y KDS) hablando con la API desde el cliente; duplicar el fetch
 * y el parseo de error en cada una era la vía rápida a dos manejos de error
 * distintos para la misma API.
 */

// Extensión explícita: estos dos módulos los carga `node --test`, que
// resuelve ESM por ruta real (mismo motivo que en `lib/carga.test.ts`).
import { type ErrorCampo, leerError } from "./errores.ts";
import { estaMuerta, marcarMuerta } from "./sesion-muerta.ts";

const BASE = "/api/proxy/api/v1";

export class ErrorApi extends Error {
  status: number;
  /** Campos que el servidor rechazó (422). Vacío en todo lo demás. */
  campos: ErrorCampo[];

  constructor(status: number, mensaje: string, campos: ErrorCampo[] = []) {
    super(mensaje);
    this.status = status;
    this.campos = campos;
  }
}

/**
 * Lo que se hace con una respuesta que no vino bien, en un solo lugar para
 * las tres funciones que salen a la red.
 *
 * El 401 es el que importa: llega solo cuando el refresco tampoco valió (ver
 * `lib/sesion-muerta.ts`), así que se anota antes de lanzar. Sin esto, el
 * KDS lo mostraba como un aviso de 4 segundos y seguía reintentando cada 3;
 * la campana lo tragaba entero; y el PDV borraba su huella de guardado y
 * reintentaba el PUT con cada tecla, en silencio.
 *
 * Con **una** excepción, y hay que declararla porque no se deduce del
 * status: los dos endpoints que juzgan una credencial —desbloquear la
 * pantalla con el PIN y pedirle autorización a un supervisor— responden 401
 * cuando el PIN está mal. Ahí el 401 es un veredicto sobre lo tecleado, no
 * sobre la sesión de quien lo teclea, y tratarlo como sesión muerta tapaba
 * el PDV entero con el aviso de "volvé a entrar" por errarle a un dígito.
 */
async function lanzar(respuesta: Response, credencial: boolean): Promise<never> {
  if (respuesta.status === 401 && !credencial) marcarMuerta();
  const { mensaje, campos } = await leerError(respuesta);
  throw new ErrorApi(respuesta.status, mensaje, campos);
}

/** Con la sesión ya muerta no se sale a la red: es lo que apaga el bucle de
 * refresco del KDS y el guardado por tecla del PDV, que si no seguirían
 * golpeando el proxy detrás del aviso hasta que alguien recargue. */
function abortarSiMuerta(): void {
  if (estaMuerta()) throw new ErrorApi(401, "Sesión expirada");
}

export async function pedir<T>(
  ruta: string,
  opciones: {
    metodo?: string;
    cuerpo?: unknown;
    /** El endpoint juzga una credencial: su 401 dice "PIN incorrecto", no
     * "tu sesión murió". Ver `lanzar`. */
    credencial?: boolean;
  } = {},
): Promise<T> {
  abortarSiMuerta();
  const respuesta = await fetch(`${BASE}${ruta}`, {
    method: opciones.metodo ?? "GET",
    headers: { "Content-Type": "application/json" },
    body: opciones.cuerpo ? JSON.stringify(opciones.cuerpo) : undefined,
  });
  if (!respuesta.ok) await lanzar(respuesta, opciones.credencial ?? false);
  // 204 (los DELETE) no traen cuerpo: pedirle `.json()` a una respuesta
  // vacía revienta con un error de sintaxis que no dice nada.
  if (respuesta.status === 204) return undefined as T;
  return (await respuesta.json()) as T;
}

/**
 * Como `pedir`, pero para una respuesta binaria — el `.xlsx` completo de un
 * reporte (ADR-083 Fase E), no las 500 filas que ya están en pantalla.
 * Aparte de `pedir` por lo mismo que `subir`: acá no hay `.json()` que
 * llamar, y el nombre de archivo sale de `Content-Disposition`, no de la
 * ruta.
 */
export async function pedirArchivo(
  ruta: string,
  opciones: { metodo?: string; cuerpo?: unknown } = {},
): Promise<{ blob: Blob; nombre: string }> {
  abortarSiMuerta();
  const respuesta = await fetch(`${BASE}${ruta}`, {
    method: opciones.metodo ?? "GET",
    headers: { "Content-Type": "application/json" },
    body: opciones.cuerpo ? JSON.stringify(opciones.cuerpo) : undefined,
  });
  if (!respuesta.ok) await lanzar(respuesta, false);
  const nombre = /filename="([^"]+)"/.exec(
    respuesta.headers.get("Content-Disposition") ?? "",
  )?.[1];
  return { blob: await respuesta.blob(), nombre: nombre ?? "reporte.xlsx" };
}

/**
 * Sube un archivo (multipart). Aparte de `pedir` porque ahí el
 * `Content-Type: application/json` está fijo, y en multipart **el navegador
 * tiene que poner el header él**: lleva un `boundary` generado al vuelo que
 * nosotros no podemos escribir. Ponerlo a mano rompe el parseo del lado del
 * servidor con un error que no menciona la palabra "boundary".
 */
export async function subir<T>(ruta: string, archivo: File): Promise<T> {
  abortarSiMuerta();
  const cuerpo = new FormData();
  cuerpo.append("archivo", archivo);
  const respuesta = await fetch(`${BASE}${ruta}`, { method: "POST", body: cuerpo });
  if (!respuesta.ok) await lanzar(respuesta, false);
  return (await respuesta.json()) as T;
}

/** Cada operación crítica necesita su clave (RN-COM-002): un reintento por
 * red inestable no puede convertirse en un segundo cobro. */
export function claveIdempotencia(prefijo: string): string {
  return `${prefijo}-${crypto.randomUUID()}`;
}
