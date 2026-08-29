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

const BASE = "/api/proxy/api/v1";

export class ErrorApi extends Error {
  status: number;

  constructor(status: number, mensaje: string) {
    super(mensaje);
    this.status = status;
  }
}

async function mensajeDeError(respuesta: Response): Promise<string> {
  try {
    const cuerpo = await respuesta.json();
    if (typeof cuerpo.detail === "string") return cuerpo.detail;
    if (Array.isArray(cuerpo.detail)) {
      return cuerpo.detail.map((d: { msg?: string }) => d.msg).join("; ");
    }
  } catch {
    // Cuerpo no-JSON: cae al mensaje genérico.
  }
  return `Error ${respuesta.status}`;
}

export async function pedir<T>(
  ruta: string,
  opciones: { metodo?: string; cuerpo?: unknown } = {},
): Promise<T> {
  const respuesta = await fetch(`${BASE}${ruta}`, {
    method: opciones.metodo ?? "GET",
    headers: { "Content-Type": "application/json" },
    body: opciones.cuerpo ? JSON.stringify(opciones.cuerpo) : undefined,
  });
  if (!respuesta.ok) {
    throw new ErrorApi(respuesta.status, await mensajeDeError(respuesta));
  }
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
  const respuesta = await fetch(`${BASE}${ruta}`, {
    method: opciones.metodo ?? "GET",
    headers: { "Content-Type": "application/json" },
    body: opciones.cuerpo ? JSON.stringify(opciones.cuerpo) : undefined,
  });
  if (!respuesta.ok) {
    throw new ErrorApi(respuesta.status, await mensajeDeError(respuesta));
  }
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
  const cuerpo = new FormData();
  cuerpo.append("archivo", archivo);
  const respuesta = await fetch(`${BASE}${ruta}`, { method: "POST", body: cuerpo });
  if (!respuesta.ok) {
    throw new ErrorApi(respuesta.status, await mensajeDeError(respuesta));
  }
  return (await respuesta.json()) as T;
}

/** Cada operación crítica necesita su clave (RN-COM-002): un reintento por
 * red inestable no puede convertirse en un segundo cobro. */
export function claveIdempotencia(prefijo: string): string {
  return `${prefijo}-${crypto.randomUUID()}`;
}
